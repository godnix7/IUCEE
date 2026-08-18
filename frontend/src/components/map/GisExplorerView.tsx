import React, { useState, useEffect, useRef } from 'react';
import { Upload, Loader2 } from 'lucide-react';
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
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
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
      if (projs.length > 0) {
        setSelectedProjectId(projs[0].id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    api.analytics.getDashboardStats().then((data) => {
      if (data.recent_analyses.length > 0) {
        // Load the most recent analysis
        const analysis = data.recent_analyses.find(a => a.status === 'completed') || data.recent_analyses[0];
        loadAnalysis(analysis);
      }
    }).catch(console.error);
  }, [selectedProjectId]);

  const loadAnalysis = async (an: ImageryAnalysis) => {
    setSelectedAnalysis(an);
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
            <div className="absolute inset-0 z-50 bg-slate-900 flex flex-col items-center justify-center text-slate-400">
              Select an analysis to explore GIS data.
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
          
          <MapLegend />
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
