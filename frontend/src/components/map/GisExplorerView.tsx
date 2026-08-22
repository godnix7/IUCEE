import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Upload, Loader2, MapPin } from 'lucide-react';
import { api } from '../../api';
import type { ImageryAnalysis, MapLayerConfig, Project } from '../../types';
import { MapView } from './MapView';
import { MapToolbar } from './MapToolbar';
import { LayerPanel } from './LayerPanel';
import { FeatureInspector } from './FeatureInspector';
import { MapLegend, CLASS_COLORS } from './MapLegend';
import { MapStatusBar } from './MapStatusBar';
import { MapCompare } from './MapCompare';
import { useToast } from '../../context/ToastContext';
import * as maplibregl from 'maplibre-gl';
import * as turf from '@turf/turf';

export const GisExplorerView: React.FC<{ onNavigateUpload: () => void }> = ({ onNavigateUpload }) => {
  const { addToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(() => {
    const saved = sessionStorage.getItem('selectedProjectId');
    return saved ? Number(saved) : null;
  });
  const [analyses, setAnalyses] = useState<ImageryAnalysis[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState<ImageryAnalysis | null>(null);
  
  const [aiGeoJson, setAiGeoJson] = useState<any>(null);
  const [osmGeoJson, setOsmGeoJson] = useState<any>(null);
  const [osmStatus, setOsmStatus] = useState<string>('');
  
  const [selectedFeature, setSelectedFeature] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [mode, setMode] = useState<'select' | 'draw' | 'distance' | 'area' | 'compare'>('select');
  const [basemap, setBasemap] = useState<'satellite' | 'streets' | 'terrain'>('satellite');
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  const mapRef = useRef<maplibregl.Map | null>(null);

  const [layers, setLayers] = useState<MapLayerConfig[]>([
    { id: 'road', label: 'Road Network', color: '#3b82f6', visible: true, opacity: 0.8, count: 0 },
    { id: 'building', label: 'Building Footprints', color: '#ef4444', visible: true, opacity: 0.8, count: 0 },
    { id: 'tree_cover', label: 'Tree Canopy Cover', color: '#22c55e', visible: true, opacity: 0.7, count: 0 },
    { id: 'water', label: 'Water Bodies', color: '#06b6d4', visible: true, opacity: 0.8, count: 0 },
    { id: 'barren_land', label: 'Barren Land', color: '#f97316', visible: true, opacity: 0.6, count: 0 },
    { id: 'agriculture', label: 'Agriculture', color: '#eab308', visible: true, opacity: 0.7, count: 0 },
    { id: 'hospital', label: 'Hospitals', color: '#ec4899', visible: true, opacity: 0.9, count: 0 },
    { id: 'school', label: 'Schools', color: '#a855f7', visible: true, opacity: 0.9, count: 0 },
    { id: 'police', label: 'Police', color: '#6366f1', visible: true, opacity: 0.9, count: 0 },
    { id: 'fire_station', label: 'Fire Stations', color: '#ea580c', visible: true, opacity: 0.9, count: 0 },
  ]);

  useEffect(() => {
    api.projects.list().then((projs) => {
      setProjects(projs);
      if (projs.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projs[0].id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedProjectId) sessionStorage.setItem('selectedProjectId', selectedProjectId.toString());
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId) return;
    api.analytics.getDashboardStats().then(async (data) => {
      setAnalyses(data.recent_analyses);
      // analysisId is carried in the URL (?analysisId=) so it survives reload / deep-links
      const urlAnalysisId = searchParams.get('analysisId');
      if (!urlAnalysisId) return;
      const id = Number(urlAnalysisId);
      let analysis = data.recent_analyses.find(a => a.id === id) || null;
      // Deep-link may reference an analysis outside the "recent" window — fetch it directly.
      if (!analysis) {
        try {
          analysis = await api.inference.getStatus(id);
          setAnalyses(prev => (prev.some(a => a.id === id) ? prev : [analysis as ImageryAnalysis, ...prev]));
        } catch {
          analysis = null;
        }
      }
      if (analysis) loadAnalysis(analysis);
    }).catch(console.error);
  }, [selectedProjectId]);

  const loadAnalysis = async (an: ImageryAnalysis) => {
    setSelectedAnalysis(an);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('analysisId', String(an.id));
      return next;
    }, { replace: true });
    setLoading(true);
    setError(null);
    setAiGeoJson(null);
    setOsmGeoJson(null);
    setSelectedFeature(null);
    
    try {
      const [aiData, osmData] = await Promise.allSettled([
        api.gis.getGeoJson(an.id),
        api.gis.getOsmGeoJson(an.id)
      ]);
      
      let aiFeats: any[] = [];
      let osmFeats: any[] = [];

      if (aiData.status === 'fulfilled') {
        setAiGeoJson(aiData.value);
        aiFeats = aiData.value.features || [];
      } else console.error("AI GeoJSON load failed", aiData.reason);

      if (osmData.status === 'fulfilled') {
        const payload = osmData.value.features ? osmData.value : { type: 'FeatureCollection', features: osmData.value };
        setOsmGeoJson(payload);
        osmFeats = payload.features || [];
      }
      
      // Update layer counts
      setLayers(prev => prev.map(l => {
         const count = l.id in CLASS_COLORS || ['road', 'building', 'tree_cover', 'water', 'barren_land', 'agriculture'].includes(l.id)
            ? aiFeats.filter((f: any) => f.properties?.class_name === l.id).length
            : osmFeats.filter((f: any) => f.properties?.category === l.id).length;
         return { ...l, count };
      }));
      
      try {
         const statusReq = await api.inference.getStatus(an.id);
         setOsmStatus((statusReq as any).osm_enrichment_status || 'pending');
      } catch (e) {
         setOsmStatus('unknown');
      }

    } catch (err: any) {
      setError(err.message || "Failed to load GIS data");
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

  const handleExport = () => {
    if (!aiGeoJson && !osmGeoJson) return addToast('No spatial data available to export.', 'info');
    
    const combined = {
      type: 'FeatureCollection',
      features: [
        ...(aiGeoJson?.features || []),
        ...(osmGeoJson?.features || [])
      ]
    };
    
    const blob = new Blob([JSON.stringify(combined, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `urbansense_export_${selectedAnalysis?.id || 'data'}.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const aiCount = aiGeoJson?.features?.length || 0;
  const osmCount = osmGeoJson?.features?.length || 0;

  return (
    <div className={`flex flex-col bg-[#0b0f19] text-white relative overflow-hidden ${isFullscreen ? 'fixed inset-0 z-50 w-screen h-screen' : 'flex-1 h-full'}`}>
      {/* Top Header/Toolbar */}
      <div className="h-12 bg-[#111827] border-b border-slate-800 flex items-center justify-between px-4 z-20 shrink-0">
        <div className="flex items-center gap-3">
          <select 
            value={selectedProjectId || ''} 
            onChange={(e) => setSelectedProjectId(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm outline-none focus:border-blue-500"
          >
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>

          <select 
            value={selectedAnalysis?.id || ''} 
            onChange={(e) => {
              const val = e.target.value;
              if (!val) {
                setSelectedAnalysis(null);
                setAiGeoJson(null);
                setOsmGeoJson(null);
                setSearchParams((prev) => {
                  const next = new URLSearchParams(prev);
                  next.delete('analysisId');
                  return next;
                }, { replace: true });
              } else {
                const an = analyses.find(a => a.id === Number(val));
                if (an) loadAnalysis(an);
              }
            }}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm outline-none focus:border-blue-500"
          >
            <option value="">Default Map (Bangalore)</option>
            {analyses.map(a => <option key={a.id} value={a.id}>Analysis #{a.id} - {a.filename}</option>)}
          </select>
          
          <button
            onClick={onNavigateUpload}
            className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium flex items-center gap-1.5 transition-colors text-xs"
          >
            <Upload size={14} /> Upload Imagery
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden relative">
        <LayerPanel 
          basemap={basemap}
          setBasemap={setBasemap}
          layers={layers}
          onToggleLayer={toggleLayerVisibility}
          onChangeOpacity={updateLayerOpacity}
          onZoomLayer={(id) => {
             if (!mapRef.current) return;
             const isOSM = !['road', 'building', 'tree_cover', 'water', 'barren_land', 'agriculture'].includes(id);
             const feats = isOSM 
                ? osmGeoJson?.features?.filter((f: any) => f.properties?.category === id)
                : aiGeoJson?.features?.filter((f: any) => f.properties?.class_name === id);
                
             if (feats && feats.length > 0) {
                const fc = turf.featureCollection(feats as any);
                const bbox = maplibregl.LngLatBounds.convert(turf.bbox(fc) as any);
                mapRef.current.fitBounds(bbox, { padding: 40 });
             } else if (selectedAnalysis?.bounds) {
                mapRef.current.fitBounds([
                   [selectedAnalysis.bounds[0], selectedAnalysis.bounds[1]],
                   [selectedAnalysis.bounds[2], selectedAnalysis.bounds[3]]
                ], { padding: 40 });
             }
          }}
        />

        <div className="flex-1 relative flex flex-col">
          {/* Overlay loading/error states */}
          {loading && (
            <div className="absolute inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex flex-col items-center justify-center">
              <Loader2 className="animate-spin text-blue-500 mb-4" size={48} />
              <p className="text-lg font-medium">Loading Geographic Data...</p>
            </div>
          )}
          
          {!loading && error && (
            <div className="absolute inset-0 z-50 bg-slate-900/80 flex flex-col items-center justify-center p-8 text-center">
              <div className="text-red-400 mb-2">Error loading map data</div>
              <div className="text-slate-300 text-sm mb-4">{error}</div>
              <button onClick={() => selectedAnalysis && loadAnalysis(selectedAnalysis)} className="px-4 py-2 bg-blue-600 rounded text-sm hover:bg-blue-500">
                Retry
              </button>
            </div>
          )}

          {!loading && !selectedAnalysis && (
            <div className="absolute inset-0 z-40 flex items-center justify-center p-6 pointer-events-none">
              <div className="pointer-events-auto bg-[#0b0f19]/92 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 max-w-md text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center mx-auto mb-3">
                  <MapPin className="text-blue-400" size={22} />
                </div>
                <h3 className="text-white font-semibold text-sm mb-1.5">GIS Explorer</h3>
                <p className="text-xs text-slate-400 leading-relaxed mb-4">
                  Overlay a completed analysis's AI-detected features (buildings, roads, water, vegetation)
                  and OpenStreetMap facilities on the live map. Toggle layers, measure distance &amp; area,
                  draw regions, and click any feature to inspect its metrics.
                </p>
                {analyses.length > 0 ? (
                  <div className="text-left">
                    <label className="block text-[11px] text-slate-500 mb-1.5">Pick an analysis to begin</label>
                    <select
                      defaultValue=""
                      onChange={(e) => { const an = analyses.find(a => a.id === Number(e.target.value)); if (an) loadAnalysis(an); }}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="" disabled>Select analysis…</option>
                      {analyses.map(a => <option key={a.id} value={a.id}>Analysis #{a.id} — {a.filename}</option>)}
                    </select>
                  </div>
                ) : (
                  <button onClick={onNavigateUpload} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium inline-flex items-center gap-1.5">
                    <Upload size={14} /> Upload imagery
                  </button>
                )}
                <p className="text-[10px] text-slate-600 mt-3">Map is centered on Bengaluru until an analysis is selected.</p>
              </div>
            </div>
          )}

          <MapToolbar 
            mode={mode}
            setMode={setMode}
            onZoomIn={() => mapRef.current?.zoomIn()}
            onZoomOut={() => mapRef.current?.zoomOut()}
            onResetView={() => selectedAnalysis && loadAnalysis(selectedAnalysis)} // Simple reset just re-fits bounds on mount (effect)
            onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
            onExport={handleExport}
          />

          {mode === 'compare' ? (
             <MapCompare 
               aiGeoJson={aiGeoJson}
               osmGeoJson={osmGeoJson}
               layers={layers}
               basemap={basemap}
                bounds={selectedAnalysis?.bounds ?? undefined}
               onFeatureSelect={setSelectedFeature}
             />
          ) : (
             <MapView 
               ref={mapRef}
               basemap={basemap}
               mode={mode}
               aiGeoJson={aiGeoJson}
               osmGeoJson={osmGeoJson}
               layers={layers}
               onFeatureSelect={setSelectedFeature}
               bounds={selectedAnalysis?.bounds ?? undefined}
               onClearDraw={() => setMode('select')}
             />
          )}
          
          <MapLegend layers={selectedAnalysis ? layers : undefined} />
        </div>

        <FeatureInspector feature={selectedFeature} onZoomFeature={(f) => {
           if (f && mapRef.current) {
              const bbox = maplibregl.LngLatBounds.convert(turf.bbox(f) as any);
              mapRef.current.fitBounds(bbox, { padding: 40 });
           }
        }} />
      </div>

      <MapStatusBar 
        analysis={selectedAnalysis} 
        aiFeatureCount={aiCount} 
        osmFeatureCount={osmCount}
        osmStatus={osmStatus}
      />
    </div>
  );
};
