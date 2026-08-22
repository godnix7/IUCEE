export interface User {
  id: number;
  email: string;
  full_name?: string;
  role: 'admin' | 'planner' | 'viewer';
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  created_by_id?: number;
  created_at: string;
  analysis_count?: number;
}

export interface SpatialFeature {
  id: number;
  analysis_id: number;
  class_name: 'road' | 'building' | 'tree_cover' | 'water' | 'barren_land' | 'hospital' | 'school' | 'slum';
  source: 'ai_segformer' | 'osm_layer';
  confidence: number;
  area_sq_meters: number;
  feature_count: number;
  geometry_json: any;
  properties?: any;
}

export type ReviewStatus = 'pending' | 'accepted' | 'needs_relabel' | 'rejected';

export interface DetectionReview {
  id: number;
  analysis_id: number;
  feature_id: number;
  reviewer_id?: number | null;
  reviewer_email?: string | null;
  original_label: string;
  original_source?: string | null;
  corrected_label?: string | null;
  review_source?: string;
  status: ReviewStatus;
  comment?: string | null;
  reviewed_at?: string | null;
}

export interface ReviewSummary {
  total_features: number;
  reviewed: number;
  pending: number;
  accepted: number;
  needs_relabel: number;
  rejected: number;
  progress_pct: number;
}

export interface AnalysisReview {
  id: number;
  analysis_id: number;
  reviewer_id?: number | null;
  reviewer_email?: string | null;
  status: 'pending' | 'accepted' | 'needs_relabel' | 'rejected';
  comment?: string | null;
  review_source?: string;
  resent?: boolean;
  resent_job_id?: number | null;
  reviewed_at?: string | null;
}

export interface ReviewListResponse {
  analysis_id: number;
  summary: ReviewSummary;
  reviews: DetectionReview[];
  image_review?: AnalysisReview | null;
}

export interface ImageryAnalysis {
  id: number;
  project_id: number;
  filename: string;
  file_path: string;
  file_type: string;
  analysis_mode?: 'segmentation' | 'detection' | 'scene_segmentation';
  original_crs?: string | null;
  normalized_crs?: string | null;
  bounds?: number[] | null;
  width?: number | null;
  height?: number | null;
  resolution_x?: number | null;
  resolution_y?: number | null;
  population_count?: number | null;
  population_source?: string | null;
  population_date?: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  inference_time_sec?: number;
  confidence_score?: number;
  error_message?: string;
  detection_summary?: {
    class_counts: Record<string, number>;
    total_detections: number;
    geo_referenced: boolean;
    model: string;
  } | null;
  detection_overlay_key?: string | null;
  created_at: string;
}

export interface PopulationData {
  count: number | null;
  source: string | null;
  date: string | null;
}

export interface AnalyticsResponse {
  analysis_id: number;
  status?: string;
  area_sq_km: number | null;
  population: PopulationData;
  infrastructure: {
    road_area_sq_m: number | null;
    road_coverage_pct: number | null;
    building_coverage_pct: number | null;
    tree_cover_pct: number | null;
    water_cover_pct: number | null;
    agriculture_cover_pct: number | null;
    barren_cover_pct: number | null;
  };
  facilities: {
    hospitals: number | null;
    schools: number | null;
    police: number | null;
    fire_stations: number | null;
  };
  normalized: {
    hospitals_per_1000: number | null;
    schools_per_1000: number | null;
  };
  score: number | null;
  component_scores: any;
  formula_version?: string | null;
  calculated_at?: string | null;
}

export interface DashboardStats {
  total_analyses: number;
  recent_analyses: ImageryAnalysis[];
  processing_queue_count: number;
  active_users_count: number;
}

export interface MapLayerConfig {
  id: string;
  label: string;
  color: string;
  visible: boolean;
  opacity: number; // 0 to 1
  count: number;
}
