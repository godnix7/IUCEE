import os
import tempfile
import traceback
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import ImageryAnalysis, ProcessingJob, SpatialFeature, OSMFeature, SpatialAnalytics
from app.services.storage_service import StorageService
from app.services.geo_service import GeoService
from app.services.ai_service import AIService
from app.services.detection_service import DetectionService
from app.services.scene_segmentation_service import SceneSegmentationService
from app.services.osm_service import OSMService
from app.services.analytics_service import AnalyticsService

logger = get_task_logger(__name__)

class StageUpdate:
    VALIDATING = "VALIDATING"
    PREPARING_RASTER = "PREPARING_RASTER"
    AI_INFERENCE = "AI_INFERENCE"
    POSTGIS_PERSISTENCE = "POSTGIS_PERSISTENCE"
    OSM_ENRICHMENT = "OSM_ENRICHMENT"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"

def update_job_status(db: Session, job: ProcessingJob, status: str = None, progress: int = None, stage: str = None, message: str = None):
    if status:
        job.status = status
    if progress is not None:
        job.progress = progress
    if stage:
        job.current_stage = stage
    if message:
        job.message = message
    
    job.last_heartbeat_at = datetime.now(timezone.utc)
    db.commit()

@celery_app.task(bind=True, name="process_imagery_analysis", max_retries=3)
def process_imagery_analysis(self, analysis_id: int, job_id: int):
    """Background task to process AI inference and OSM enrichment."""
    db = SessionLocal()
    temp_file_path = None
    
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
        
        if not job or not analysis:
            logger.error(f"Job {job_id} or Analysis {analysis_id} not found.")
            return

        # Check for cancellation
        if job.status == "cancelled":
            logger.info(f"Job {job_id} is cancelled. Aborting.")
            return

        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        update_job_status(db, job, status="running", progress=0, stage=StageUpdate.VALIDATING, message="Starting job")

        # 1. Download file from MinIO
        update_job_status(db, job, progress=5, stage=StageUpdate.PREPARING_RASTER, message="Downloading image from storage")
        object_key = analysis.file_path
        _, ext = os.path.splitext(object_key)
        
        fd, temp_file_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        
        try:
            StorageService.download_file(object_key, temp_file_path)
        except Exception as e:
            raise Exception(f"Failed to download source image: {e}")

        # 2. Extract Metadata
        try:
            meta = GeoService.read_raster_metadata(temp_file_path)
            transform = meta["transform"]
        except Exception as e:
            # Deterministic failure (INVALID_GEOTIFF), don't retry
            job.error_code = "INVALID_GEOTIFF"
            raise ValueError(f"Invalid GeoTIFF or missing CRS: {e}")
            
        bounds = tuple(analysis.bounds) if analysis.bounds else None

        mode = (analysis.analysis_mode or "segmentation").lower()

        # 3. AI Inference — routed by analysis mode
        update_job_status(db, job, progress=10, stage=StageUpdate.AI_INFERENCE,
                          message=f"Running AI Inference ({mode})")

        def progress_callback(processed, total):
            # AI Inference is 10-70% (range of 60%)
            pct = 10 + int(60 * (processed / max(total, 1)))
            update_job_status(db, job, progress=pct, message=f"Processed {processed} of {total} tiles")

        detection_overlay_path = None
        class_counts = {}          # detection: counts per class ; scene_seg: coverage % per class
        overlay_is_image = mode in ("detection", "scene_segmentation")
        try:
            if mode == "detection":
                detection_overlay_path = temp_file_path + "_overlay.jpg"
                ai_features, avg_conf, inf_time, tiles, class_counts = DetectionService.run_detection(
                    temp_file_path, transform, meta,
                    annotated_out_path=detection_overlay_path,
                    progress_callback=progress_callback,
                )
            elif mode == "scene_segmentation":
                detection_overlay_path = temp_file_path + "_overlay.jpg"
                ai_features, avg_conf, inf_time, tiles, class_counts = SceneSegmentationService.run_scene_segmentation(
                    temp_file_path, transform, meta,
                    annotated_out_path=detection_overlay_path,
                    progress_callback=progress_callback,
                )
            else:
                ai_features, avg_conf, inf_time, tiles = AIService.run_inference(
                    temp_file_path, transform, meta, progress_callback=progress_callback, job_id=job_id
                )
        except Exception as e:
            job.error_code = "AI_INFERENCE_FAILED"
            raise Exception(f"AI Inference failed: {e}")

        # 4. PostGIS Persistence
        update_job_status(db, job, progress=70, stage=StageUpdate.POSTGIS_PERSISTENCE, message="Saving spatial features")

        # Clean existing features for idempotency
        db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis.id).delete()

        created_features = []
        for feat_dict in ai_features:
            feat = SpatialFeature(
                analysis_id=analysis.id,
                class_name=feat_dict["class_name"],
                source=feat_dict["source"],
                confidence=feat_dict["confidence"],
                area_sq_meters=feat_dict["area_sq_meters"],
                feature_count=feat_dict["feature_count"],
                geometry=f"SRID=4326;{feat_dict['geometry_wkt']}",
                model_name=feat_dict.get("model_name"),
                model_version=feat_dict.get("model_version"),
                properties=feat_dict.get("properties"),
            )
            db.add(feat)
            created_features.append(feat)
        db.commit()

        # Detection / scene-segmentation modes: upload the annotated overlay image to MinIO,
        # store a summary, and skip land-cover OSM enrichment + analytics (which are for
        # georeferenced nadir land-cover segmentation only).
        if overlay_is_image:
            sub = "detection" if mode == "detection" else "scene"
            if detection_overlay_path and os.path.exists(detection_overlay_path):
                overlay_key = f"analyses/{analysis.id}/{sub}/overlay.jpg"
                try:
                    StorageService.upload_file(detection_overlay_path, overlay_key)
                    analysis.detection_overlay_key = overlay_key
                finally:
                    try:
                        os.remove(detection_overlay_path)
                    except OSError:
                        pass
            if mode == "detection":
                analysis.detection_summary = {
                    "summary_type": "detection_counts",
                    "class_counts": class_counts,
                    "total_detections": int(sum(class_counts.values())),
                    "geo_referenced": bool(analysis.original_crs),
                    "model": settings.DETECTION_MODEL,
                }
                done_msg = "Detection completed successfully"
            else:
                analysis.detection_summary = {
                    "summary_type": "scene_coverage_pct",
                    "class_counts": class_counts,   # coverage % per class
                    "geo_referenced": bool(analysis.original_crs),
                    "model": settings.SCENE_SEG_MODEL,
                }
                done_msg = "Scene segmentation completed successfully"
            analysis.status = "completed"
            analysis.confidence_score = avg_conf
            analysis.inference_time_sec = inf_time
            analysis.osm_enrichment_status = "skipped"
            job.completed_at = datetime.now(timezone.utc)
            update_job_status(db, job, status="completed", progress=100,
                              stage=StageUpdate.COMPLETED, message=done_msg)
            db.commit()
            return
        
        # 5. OSM Enrichment (only possible when the image is truly georeferenced)
        update_job_status(db, job, progress=85, stage=StageUpdate.OSM_ENRICHMENT, message="Fetching OSM Data")

        existing_osm_features = []
        if not bounds:
            # No real geographic bounds -> OSM enrichment is meaningless. Skip cleanly
            # instead of querying a hardcoded default city.
            logger.info("Skipping OSM enrichment: analysis has no geographic bounds.")
            analysis.osm_enrichment_status = "skipped"
            db.commit()
        else:
            try:
                # fetch_osm_enrichment returns a 5-tuple:
                # (features, status, error_message, categories_requested, categories_completed)
                osm_features, osm_status, osm_err, _req, _done = OSMService.fetch_osm_enrichment(bounds)

                # Idempotency
                db.query(OSMFeature).filter(OSMFeature.analysis_id == analysis.id).delete()

                for o_feat in osm_features:
                    geom = o_feat["geometry"]  # shapely geometry
                    geom_wkt = geom.wkt if hasattr(geom, "wkt") else str(geom)
                    db_feat = OSMFeature(
                        analysis_id=analysis.id,
                        osm_type=o_feat.get("osm_type", "node"),
                        osm_id=o_feat["osm_id"],
                        category=o_feat["category"],
                        name=o_feat.get("name"),
                        tags=o_feat.get("tags", {}),
                        geometry=f"SRID=4326;{geom_wkt}"
                    )
                    db.add(db_feat)
                    existing_osm_features.append(db_feat)
                db.commit()
                analysis.osm_enrichment_status = osm_status or "completed"
                if osm_err:
                    logger.info(f"OSM enrichment note: {osm_err}")
            except Exception as e:
                logger.warning(f"OSM Enrichment failed: {e}")
                analysis.osm_enrichment_status = "failed"
                # We DO NOT fail the job if OSM fails. We isolate the failure.
                db.commit()

        # 6. Finalizing Analytics
        update_job_status(db, job, progress=95, stage=StageUpdate.FINALIZING, message="Calculating Spatial Analytics")
        
        # Calculate analytics directly using PostGIS logic
        analytics_dict = AnalyticsService.calculate_analytics(
            db=db,
            analysis_id=analysis.id,
            population_count=analysis.population_count,
            population_source=analysis.population_source,
            population_date=analysis.population_date
        )

        from app.models import SpatialAnalytics
        db.query(SpatialAnalytics).filter(SpatialAnalytics.analysis_id == analysis.id).delete()
        
        if "status" not in analytics_dict or analytics_dict["status"] != "no_data":
            analytics_record = SpatialAnalytics(
                analysis_id=analysis.id,
                population_count=analytics_dict["population_count"],
                population_source=analytics_dict["population_source"],
                population_date=analytics_dict["population_date"],
                analysis_area_sq_km=analytics_dict["analysis_area_sq_km"],
                road_area_sq_m=analytics_dict["road_area_sq_m"],
                road_coverage_pct=analytics_dict["road_coverage_pct"],
                building_area_sq_m=analytics_dict["building_area_sq_m"],
                building_coverage_pct=analytics_dict["building_coverage_pct"],
                tree_area_sq_m=analytics_dict["tree_area_sq_m"],
                tree_cover_pct=analytics_dict["tree_cover_pct"],
                water_area_sq_m=analytics_dict["water_area_sq_m"],
                water_cover_pct=analytics_dict["water_cover_pct"],
                barren_area_sq_m=analytics_dict["barren_area_sq_m"],
                barren_cover_pct=analytics_dict["barren_cover_pct"],
                agriculture_area_sq_m=analytics_dict["agriculture_area_sq_m"],
                agriculture_cover_pct=analytics_dict["agriculture_cover_pct"],
                hospital_count=analytics_dict["hospital_count"],
                school_count=analytics_dict["school_count"],
                police_count=analytics_dict["police_count"],
                fire_station_count=analytics_dict["fire_station_count"],
                hospitals_per_1000=analytics_dict["hospitals_per_1000"],
                schools_per_1000=analytics_dict["schools_per_1000"],
                infrastructure_score=analytics_dict["infrastructure_score"],
                component_scores=analytics_dict["component_scores"],
                formula_version=analytics_dict["formula_version"]
            )
            db.add(analytics_record)

        analysis.status = "completed"
        analysis.confidence_score = avg_conf
        analysis.inference_time_sec = inf_time
        
        job.completed_at = datetime.now(timezone.utc)
        update_job_status(db, job, status="completed", progress=100, stage=StageUpdate.COMPLETED, message="Job completed successfully")
        
        AIService.cleanup_job_cache(job_id)
        
        # We don't delete the MinIO object, it's the original source image.
        
    except ValueError as e:
        # Deterministic errors should not be retried
        logger.error(f"Deterministic error in Job {job_id}: {e}")
        db.rollback()
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
        if job:
            job.status = "failed"
            job.failed_at = datetime.now(timezone.utc)
            if not job.error_code:
                job.error_code = "VALIDATION_FAILED"
            job.error_message = str(e)
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
        db.commit()
        AIService.cleanup_job_cache(job_id)
    except Exception as e:
        logger.error(f"Error in Job {job_id}: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            if self.request.retries < self.max_retries:
                job.attempt += 1
                update_job_status(db, job, status="retrying", message=f"Retrying after error: {e}")
                
                # Cleanup temp file before retry
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                        
                raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries)) # Exponential backoff
            else:
                job.status = "failed"
                job.failed_at = datetime.now(timezone.utc)
                job.error_code = job.error_code or "PROCESSING_FAILED"
                job.error_message = str(e)
                
                analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
                if analysis:
                    analysis.status = "failed"
                    analysis.error_message = str(e)
                db.commit()
                AIService.cleanup_job_cache(job_id)
    finally:
        db.close()
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file_path}: {e}")
