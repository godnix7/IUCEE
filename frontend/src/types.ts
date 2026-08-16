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
  refresh_token: string;
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

export interface UrbanBenchmark {
  id: number;
  analysis_id: number;
  population_count: number;
  road_density_km_per_sqkm: number;
  building_coverage_pct: number;
  tree_cover_pct: number;
  water_cover_pct: number;
  built_up_ratio: number;
  hospitals_per_10k_pop: number;
  schools_per_10k_pop: number;
  infrastructure_score: number;
  created_at: string;
}

export interface ImageryAnalysis {
  id: number;
  project_id: number;
  filename: string;
  file_path: string;
  file_type: string;
  crs: string;
  bounds?: number[];
  width?: number;
  height?: number;
  population_estimate: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  inference_time_sec?: number;
  confidence_score?: number;
  error_message?: string;
  created_at: string;
  benchmark?: UrbanBenchmark;
}

export interface DashboardStats {
  total_analyses: number;
  infrastructure_coverage_pct: number;
  roads_detected_km: number;
  buildings_detected_count: number;
  water_bodies_count: number;
  tree_coverage_pct: number;
  population_mapped: number;
  infrastructure_score: number;
  benchmark_status: string;
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
