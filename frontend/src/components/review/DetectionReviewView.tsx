import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, ImageOff } from 'lucide-react';
import * as maplibregl from 'maplibre-gl';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { ImageryAnalysis, AnalysisReview, MapLayerConfig } from '../../types';
import { MapView } from '../map/MapView';
import { CLASS_COLORS, CLASS_LABELS } from '../map/MapLegend';
import { ReviewSummaryBar } from './ReviewSummaryBar';
import { ImageVerdictBar } from './ImageVerdictBar';
import { DetectionReviewPanel, type ReviewFeature } from './DetectionReviewPanel';
import { DetectionInspector } from './DetectionInspector';

export const DetectionReviewView: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>();
  const id = Number(analysisId);
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { user } = useAuth();
  const canEdit = user?.role === 'admin' || user?.role === 'planner';

  const [analysis, setAnalysis] = useState<ImageryAnalysis | null>(null);
  const [features, setFeatures] = useState<ReviewFeature[]>([]);
  const [aiGeoJson, setAiGeoJson] = useState<any>(null);
  const [imageReview, setImageReview] = useState<AnalysisReview | null>(null);
  const [overlayUrl, setOverlayUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [hoveredClass, setHoveredClass] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const mapRef = useRef<maplibregl.Map | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isImageOverlay = analysis?.analysis_mode === 'detection'
    || analysis?.analysis_mode === 'scene_segmentation'
    || !!analysis?.detection_overlay_key;
  const hasBounds = Array.isArray(analysis?.bounds) && analysis!.bounds!.length === 4;

  const load = async () => {
    setError('');
    try {
      const [an, geo, rev] = await Promise.all([
        api.inference.getStatus(id),
        api.gis.getGeoJson(id).catch(() => ({ features: [] })),
        api.review.list(id).catch(() => ({ image_review: null } as any)),
      ]);
      setAnalysis(an);
      setAiGeoJson(geo);
      setImageReview(rev.image_review || null);

      const feats: ReviewFeature[] = (geo.features || [])
        .map((f: any) => f.properties)
        .filter((p: any) => p && typeof p.id === 'number')
        .map((p: any) => ({
          id: p.id, class_name: p.class_name, source: p.source, confidence: p.confidence,
          area_sq_meters: p.area_sq_meters, feature_count: p.feature_count,
          model_name: p.model_name, model_version: p.model_version,
          coverage_pct: typeof p.coverage_pct === 'number' ? p.coverage_pct : undefined,
        }));
      setFeatures(feats);
      setVisible((prev) => {
        const next = { ...prev };
        feats.forEach((f) => { if (!(f.class_name in next)) next[f.class_name] = true; });
        return next;
      });

      if ((an.analysis_mode === 'detection' || an.analysis_mode === 'scene_segmentation' || an.detection_overlay_key) && an.status === 'completed') {
        api.inference.getDetectionOverlayUrl(id).then((u) => { setOverlayUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return u; }); }).catch(() => {});
      }
      return an;
    } catch (e: any) {
      setError(e.message || 'Unable to load detection results.');
      return null;
    }
  };

  useEffect(() => {
    if (!Number.isFinite(id)) { setError('Invalid analysis id'); setLoading(false); return; }
    setLoading(true);
    load().finally(() => setLoading(false));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      setOverlayUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const modelName = features[0]?.model_name || analysis?.detection_summary?.model || null;

  const layers: MapLayerConfig[] = useMemo(() => features.map((f) => ({
    id: f.class_name, label: CLASS_LABELS[f.class_name] || f.class_name,
    color: CLASS_COLORS[f.class_name] || '#94a3b8', visible: visible[f.class_name] !== false,
    opacity: 0.8, count: f.feature_count ?? 0,
  })), [features, visible]);

  // Poll while a re-sent image is reprocessing
  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const an = await load();
      if (an && (an.status === 'completed' || an.status === 'failed')) {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 3000);
  };

  const submitVerdict = async (status: 'accepted' | 'needs_relabel' | 'rejected', comment: string) => {
    setSaving(true);
    try {
      const r = await api.review.imageReview(id, { status, comment: comment || null });
      setImageReview(r);
      if (status === 'needs_relabel') {
        addToast(`Whole image re-sent for reprocessing (job #${r.resent_job_id})`, 'success');
        await load();
        startPolling();
      } else {
        addToast(`Image marked as ${status}`, 'success');
      }
    } catch (e: any) {
      addToast(e.message || 'Failed to submit verdict', 'error');
    } finally {
      setSaving(false);
    }
  };

  const toggleVisible = (cls: string) => setVisible((v) => ({ ...v, [cls]: v[cls] === false }));
  const isolate = (cls: string) => setVisible(Object.fromEntries(features.map((f) => [f.class_name, f.class_name === cls])));
  const showAll = () => setVisible(Object.fromEntries(features.map((f) => [f.class_name, true])));
  const hideAll = () => setVisible(Object.fromEntries(features.map((f) => [f.class_name, false])));

  const selectedFeature = features.find((f) => f.id === selectedId) || null;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0b0f19] text-slate-300">
        <Loader2 className="animate-spin text-blue-500 mr-3" size={28} /> Loading detection results…
      </div>
    );
  }
  if (error || !analysis) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#0b0f19] text-slate-300 gap-3">
        <ImageOff size={36} className="text-slate-600" />
        <div className="text-sm">{error || 'Unable to load detection results.'}</div>
        <button onClick={() => { setLoading(true); load().finally(() => setLoading(false)); }} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs">Retry</button>
      </div>
    );
  }

  const reprocessing = analysis.status !== 'completed' && analysis.status !== 'failed';

  return (
    <div className="flex-1 flex flex-col bg-[#0b0f19] overflow-hidden">
      <ReviewSummaryBar analysis={analysis} modelName={modelName} classCount={features.length} onBack={() => navigate('/dashboard')} />
      <ImageVerdictBar review={imageReview} canEdit={canEdit} saving={saving} onVerdict={submitVerdict} />

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col relative overflow-hidden">
          <div className="flex-1 relative">
            {reprocessing ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 gap-2">
                <Loader2 className="animate-spin text-amber-500" size={26} />
                <span className="text-sm">Reprocessing re-sent image… ({analysis.status})</span>
              </div>
            ) : isImageOverlay ? (
              overlayUrl ? (
                <div className="absolute inset-0 overflow-auto bg-slate-950 flex items-center justify-center p-4">
                  <img src={overlayUrl} alt="AI overlay" className="max-w-full max-h-full rounded-lg border border-slate-800" />
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">Loading overlay…</div>
              )
            ) : hasBounds ? (
              <MapView
                ref={mapRef} basemap="satellite" mode="select"
                aiGeoJson={aiGeoJson} osmGeoJson={{ type: 'FeatureCollection', features: [] }}
                layers={layers} bounds={analysis.bounds ?? undefined}
                highlightClass={hoveredClass}
                onFeatureSelect={(f: any) => { if (f?.properties?.id != null) setSelectedId(Number(f.properties.id)); }}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-center text-slate-500 text-sm px-8">
                This analysis is not georeferenced, so its geometry is in pixel space and cannot be shown on a geographic map.
                Use the class list on the right to review detections.
              </div>
            )}
          </div>

          <div className="border-t border-slate-800 bg-[#0e1420] max-h-56 overflow-y-auto">
            <div className="px-4 pt-2.5 flex flex-wrap gap-x-4 gap-y-1">
              {features.length === 0 && <span className="text-[11px] text-slate-500">No features available</span>}
              {features.map((f) => (
                <span key={f.id} className="inline-flex items-center gap-1.5 text-[11px] text-slate-300">
                  <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: CLASS_COLORS[f.class_name] || '#94a3b8' }} />
                  {CLASS_LABELS[f.class_name] || f.class_name}
                  <span className="text-slate-500">· {typeof f.coverage_pct === 'number' ? `${f.coverage_pct}%` : (f.feature_count ?? 0)}</span>
                </span>
              ))}
            </div>
            <DetectionInspector feature={selectedFeature} review={null} analysis={analysis} />
          </div>
        </div>

        <DetectionReviewPanel
          features={features} visible={visible} selectedId={selectedId}
          onToggleVisible={toggleVisible} onIsolate={isolate} onShowAll={showAll} onHideAll={hideAll} onSelect={setSelectedId}
          onHoverClass={setHoveredClass}
        />
      </div>
    </div>
  );
};
