import React, { useState, useEffect } from 'react';
import {
  Layers, Upload, Play, Download, Maximize2, Eye, EyeOff, Info, Compass, Ruler, Edit3,
  SplitSquareVertical, MapPin
} from 'lucide-react';
import { api } from '../../api';
import type { ImageryAnalysis, MapLayerConfig, Project } from '../../types';

export const GisExplorerView: React.FC<{ onNavigateUpload: () => void }> = ({ onNavigateUpload }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedAnalysis, setSelectedAnalysis] = useState<ImageryAnalysis | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [measureMode, setMeasureMode] = useState<'none' | 'draw' | 'distance' | 'area'>('none');
  const [compareMode, setCompareMode] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [layers, setLayers] = useState<MapLayerConfig[]>([
    { id: 'road', label: 'Road Network', color: '#3b82f6', visible: true, opacity: 0.8, count: 12 },
    { id: 'building', label: 'Building Footprints', color: '#ef4444', visible: true, opacity: 0.8, count: 48 },
    { id: 'tree_cover', label: 'Tree Canopy Cover', color: '#22c55e', visible: true, opacity: 0.7, count: 24 },
    { id: 'water', label: 'Water Bodies', color: '#06b6d4', visible: true, opacity: 0.8, count: 5 },
    { id: 'hospital', label: 'Hospitals (OSM)', color: '#ec4899', visible: true, opacity: 0.9, count: 2 },
    { id: 'school', label: 'Schools (OSM)', color: '#eab308', visible: true, opacity: 0.9, count: 4 },
    { id: 'slum', label: 'Informal Settlements', color: '#a855f7', visible: true, opacity: 0.7, count: 1 },
    { id: 'barren_land', label: 'Open Barren Land', color: '#f97316', visible: true, opacity: 0.6, count: 8 },
  ]);

  useEffect(() => {
    api.projects.list().then((projs) => {
      setProjects(projs);
      if (projs.length > 0) {
        setSelectedProjectId(projs[0].id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    api.analytics.getDashboardStats().then((data) => {
      if (data.recent_analyses.length > 0) {
        loadAnalysis(data.recent_analyses[0]);
      }
    }).catch(console.error);
  }, [selectedProjectId]);

  const loadAnalysis = async (an: ImageryAnalysis) => {
    setSelectedAnalysis(an);
    setLoading(true);
    try {
      const data = await api.gis.getGeoJson(an.id);
      if (data.features && data.features.length > 0) {
        setSelectedFeature(data.features[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleLayerVisibility = (layerId: string) => {
    setLayers(layers.map(l => l.id === layerId ? { ...l, visible: !l.visible } : l));
  };

  const updateLayerOpacity = (layerId: string, opacity: number) => {
    setLayers(layers.map(l => l.id === layerId ? { ...l, opacity } : l));
  };

  return (
    <div className={`flex-1 flex flex-col bg-[#0b0f19] text-white relative overflow-hidden ${isFullscreen ? 'fixed inset-0 z-50' : 'h-full'}`}>
      <div className="h-12 bg-[#111827] border-b border-slate-800 flex items-center justify-between px-4 z-20 text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={onNavigateUpload}
            className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium flex items-center gap-1.5 transition-colors"
          >
            <Upload size={14} /> Upload Imagery
          </button>
          
          <button
            onClick={() => selectedAnalysis && loadAnalysis(selectedAnalysis)}
            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded font-medium flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <Play size={14} className="text-emerald-400" /> Re-Run AI
          </button>

          <div className="h-4 w-px bg-slate-800 my-auto" />

          <ToolButton
            icon={<Edit3 size={14} />}
            label="Draw Polygon"
            active={measureMode === 'draw'}
            onClick={() => setMeasureMode(measureMode === 'draw' ? 'none' : 'draw')}
          />
          <ToolButton
            icon={<Ruler size={14} />}
            label="Distance"
            active={measureMode === 'distance'}
            onClick={() => setMeasureMode(measureMode === 'distance' ? 'none' : 'distance')}
          />
          <ToolButton
            icon={<Compass size={14} />}
            label="Area Measure"
            active={measureMode === 'area'}
            onClick={() => setMeasureMode(measureMode === 'area' ? 'none' : 'area')}
          />
          <ToolButton
            icon={<SplitSquareVertical size={14} />}
            label="Compare Swipe"
            active={compareMode}
            onClick={() => setCompareMode(!compareMode)}
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 border border-slate-700"
            title="Toggle Fullscreen"
          >
            <Maximize2 size={14} />
          </button>

          {selectedAnalysis && (
            <a
              href={api.reports.downloadPdfUrl(selectedAnalysis.id)}
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded font-medium flex items-center gap-1.5"
            >
              <Download size={14} /> Export PDF Report
            </a>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden relative">
        <div className="w-72 bg-[#111827] border-r border-slate-800 flex flex-col z-10">
          <div className="p-3 border-b border-slate-800">
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Select Project</label>
            <select
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 p-3 overflow-y-auto space-y-3">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center justify-between">
              <span>GIS Layers & Classes</span>
              <Layers size={14} className="text-blue-400" />
            </h4>

            <div className="space-y-2">
              {layers.map((l) => (
                <div key={l.id} className="bg-slate-900/80 border border-slate-800/80 rounded p-2 text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: l.color }} />
                      <span className="font-medium text-slate-200">{l.label}</span>
                    </div>

                    <button
                      onClick={() => toggleLayerVisibility(l.id)}
                      className={`p-1 rounded ${l.visible ? 'text-blue-400 bg-blue-500/10' : 'text-slate-600'}`}
                    >
                      {l.visible ? <Eye size={14} /> : <EyeOff size={14} />}
                    </button>
                  </div>

                  {l.visible && (
                    <div className="flex items-center gap-2 pt-1 border-t border-slate-800/50">
                      <span className="text-[10px] text-slate-500">Opacity</span>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={l.opacity}
                        onChange={(e) => updateLayerOpacity(l.id, parseFloat(e.target.value))}
                        className="flex-1 accent-blue-500 h-1 bg-slate-800 rounded cursor-pointer"
                      />
                      <span className="text-[10px] text-slate-400">{Math.round(l.opacity * 100)}%</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex-1 bg-[#090d16] relative flex items-center justify-center overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40 pointer-events-none" />

          <div className="relative w-full h-full p-8 flex items-center justify-center">
            {loading ? (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex items-center gap-3 text-blue-400 shadow-2xl z-30">
                <Compass className="animate-spin" size={20} />
                <span className="text-xs">Fetching GeoJSON spatial vector features...</span>
              </div>
            ) : (
              <div className="w-full h-full max-w-4xl max-h-[600px] border border-blue-500/30 rounded-2xl bg-slate-900/60 backdrop-blur shadow-2xl relative overflow-hidden p-6 flex flex-col justify-between">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <MapPin className="text-blue-400" size={16} />
                    <span className="text-xs font-semibold text-white">
                      {selectedAnalysis ? selectedAnalysis.filename : 'Metropolitan Infrastructure Tile'}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/30 text-blue-400 text-[10px]">
                      EPSG:4326 WGS84
                    </span>
                  </div>

                  <span className="text-[11px] text-slate-400">
                    Lat: 12.9716 N | Lon: 77.5946 E
                  </span>
                </div>

                <div className="flex-1 my-4 relative flex items-center justify-center">
                  <svg className="w-full h-full max-h-96" viewBox="0 0 800 400">
                    {layers.find(l => l.id === 'road')?.visible && (
                      <path
                        d="M 50,200 Q 200,100 400,220 T 750,180"
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth="12"
                        opacity={layers.find(l => l.id === 'road')?.opacity}
                        className="hover:stroke-blue-400 cursor-pointer transition-colors"
                        onClick={() => setSelectedFeature({ class_name: 'road', area_sq_meters: 14200, confidence: 0.94, count: 12 })}
                      />
                    )}

                    {layers.find(l => l.id === 'building')?.visible && (
                      <g opacity={layers.find(l => l.id === 'building')?.opacity}>
                        <rect x="120" y="80" width="70" height="60" rx="4" fill="#ef4444" opacity="0.8" stroke="#fca5a5" strokeWidth="1" className="hover:opacity-100 cursor-pointer" onClick={() => setSelectedFeature({ class_name: 'building', area_sq_meters: 4200, confidence: 0.91, count: 48 })} />
                        <rect x="220" y="70" width="90" height="80" rx="4" fill="#ef4444" opacity="0.8" stroke="#fca5a5" strokeWidth="1" className="hover:opacity-100 cursor-pointer" onClick={() => setSelectedFeature({ class_name: 'building', area_sq_meters: 7200, confidence: 0.89, count: 48 })} />
                        <rect x="480" y="240" width="110" height="90" rx="4" fill="#ef4444" opacity="0.8" stroke="#fca5a5" strokeWidth="1" className="hover:opacity-100 cursor-pointer" onClick={() => setSelectedFeature({ class_name: 'building', area_sq_meters: 9900, confidence: 0.95, count: 48 })} />
                      </g>
                    )}

                    {layers.find(l => l.id === 'tree_cover')?.visible && (
                      <circle cx="340" cy="280" r="55" fill="#22c55e" opacity={layers.find(l => l.id === 'tree_cover')?.opacity} className="hover:opacity-100 cursor-pointer" onClick={() => setSelectedFeature({ class_name: 'tree_cover', area_sq_meters: 9500, confidence: 0.88, count: 24 })} />
                    )}

                    {layers.find(l => l.id === 'hospital')?.visible && (
                      <rect x="620" y="90" width="80" height="80" rx="6" fill="#ec4899" opacity={layers.find(l => l.id === 'hospital')?.opacity} stroke="#fbcfe8" strokeWidth="2" className="hover:opacity-100 cursor-pointer" onClick={() => setSelectedFeature({ class_name: 'hospital', area_sq_meters: 6400, confidence: 1.0, count: 2 })} />
                    )}
                  </svg>
                </div>

                <div className="text-[11px] text-slate-500 flex items-center justify-between border-t border-slate-800 pt-2">
                  <span>Interactive MapLibre GIS Engine Engine Mode: Active</span>
                  <span>Scale 1:5,000 | Ground Resolution 0.25m/px</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="w-72 bg-[#111827] border-l border-slate-800 p-4 flex flex-col z-10 text-xs">
          <h4 className="font-semibold text-white mb-3 flex items-center gap-2 border-b border-slate-800 pb-2">
            <Info size={14} className="text-blue-400" /> Feature Inspector
          </h4>

          {selectedFeature ? (
            <div className="space-y-3 flex-1">
              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Class Category</span>
                  <span className="font-bold text-white capitalize">{selectedFeature.class_name?.replace('_', ' ')}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Area Footprint</span>
                  <span className="font-medium text-emerald-400">{selectedFeature.area_sq_meters?.toLocaleString()} m²</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400">AI Confidence</span>
                  <span className="font-medium text-blue-400">{Math.round((selectedFeature.confidence || 0.9) * 100)}%</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Source Engine</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-slate-800 rounded text-slate-300">
                    {selectedFeature.source || 'SegFormer AI'}
                  </span>
                </div>
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Geographic Bounding Box</span>
                <p className="text-[11px] text-slate-300 font-mono">Min: [77.580, 12.960]</p>
                <p className="text-[11px] text-slate-300 font-mono">Max: [77.600, 12.980]</p>
              </div>
            </div>
          ) : (
            <p className="text-slate-500 text-center my-auto">Select any polygon feature on the map to inspect properties.</p>
          )}
        </div>
      </div>
    </div>
  );
};

const ToolButton: React.FC<{ icon: React.ReactNode; label: string; active?: boolean; onClick: () => void }> = ({
  icon, label, active, onClick
}) => (
  <button
    onClick={onClick}
    className={`px-2 py-1 rounded flex items-center gap-1 transition-colors ${
      active ? 'bg-blue-600 text-white font-medium' : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
    }`}
  >
    {icon} <span>{label}</span>
  </button>
);
