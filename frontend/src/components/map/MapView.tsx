import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as turf from '@turf/turf';
import type { MapLayerConfig } from '../../types';
import { CLASS_COLORS } from './MapLegend';

interface MapViewProps {
  aiGeoJson: any;
  osmGeoJson: any;
  layers: MapLayerConfig[];
  basemap: 'satellite' | 'streets' | 'terrain';
  mode: 'select' | 'draw' | 'distance' | 'area' | 'compare';
  onFeatureSelect: (feature: any) => void;
  bounds?: number[]; // [minX, minY, maxX, maxY]
  onClearDraw?: () => void;
}

const BASEMAP_STYLES = {
  satellite: {
    version: 8,
    sources: {
      'esri-satellite': {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256
      }
    },
    layers: [{ id: 'satellite', type: 'raster', source: 'esri-satellite', minzoom: 0, maxzoom: 22 }]
  },
  streets: {
    version: 8,
    sources: {
      'osm': {
        type: 'raster',
        tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256
      }
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19 }]
  },
  terrain: {
    version: 8,
    sources: {
      'terrain-source': {
        type: 'raster',
        tiles: ['https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg'],
        tileSize: 256
      }
    },
    layers: [{ id: 'terrain', type: 'raster', source: 'terrain-source', minzoom: 0, maxzoom: 18 }]
  }
};

export const MapView = React.forwardRef<maplibregl.Map | null, MapViewProps>(({
  aiGeoJson, osmGeoJson, layers, basemap, mode, onFeatureSelect, bounds, onClearDraw
}, ref) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const drawLayerIds = useRef<string[]>([]);
  const measurementSourceId = 'measurement-source';
  const drawSourceId = 'draw-source';

  const [currentDrawCoords, setCurrentDrawCoords] = useState<any[]>([]);
  const [drawResult, setDrawResult] = useState<{ text: string, type: string, coords: any[] } | null>(null);

  // Initialize Map
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAP_STYLES[basemap] as any,
      center: [77.5946, 12.9716], // Default Bangalore
      zoom: 12,
      attributionControl: false
    });

    mapInstance.current = map;
    if (typeof ref === 'function') ref(map);
    else if (ref) ref.current = map;

    map.on('load', () => {
      setMapLoaded(true);

      // Add sources
      map.addSource('ai-data', { type: 'geojson', data: aiGeoJson || { type: 'FeatureCollection', features: [] } });
      map.addSource('osm-data', { type: 'geojson', data: osmGeoJson || { type: 'FeatureCollection', features: [] } });
      
      map.addSource(measurementSourceId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addSource(drawSourceId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });

      // Add Measurement/Draw Layers
      map.addLayer({
        id: 'measure-lines',
        type: 'line',
        source: measurementSourceId,
        paint: { 'line-color': '#ffea00', 'line-width': 2, 'line-dasharray': [2, 2] }
      });
      map.addLayer({
        id: 'measure-points',
        type: 'circle',
        source: measurementSourceId,
        paint: { 'circle-radius': 4, 'circle-color': '#ffea00' }
      });
      map.addLayer({
        id: 'draw-polygon-fill',
        type: 'fill',
        source: drawSourceId,
        paint: { 'fill-color': '#00ff00', 'fill-opacity': 0.2 }
      });
      map.addLayer({
        id: 'draw-polygon-stroke',
        type: 'line',
        source: drawSourceId,
        paint: { 'line-color': '#00ff00', 'line-width': 2 }
      });
      map.addLayer({
        id: 'draw-lines',
        type: 'line',
        source: drawSourceId,
        paint: { 'line-color': '#00ff00', 'line-width': 2, 'line-dasharray': [2, 2] }
      });

      addDataLayers(map, layers);
    });

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Sync Basemap
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current) return;
    mapInstance.current.setStyle(BASEMAP_STYLES[basemap] as any);
    
    // style change resets sources and layers, need to re-add them after style load
    mapInstance.current.once('styledata', () => {
      if (!mapInstance.current?.getSource('ai-data')) {
        mapInstance.current?.addSource('ai-data', { type: 'geojson', data: (aiGeoJson || { type: 'FeatureCollection', features: [] }) as any });
        mapInstance.current?.addSource('osm-data', { type: 'geojson', data: (osmGeoJson || { type: 'FeatureCollection', features: [] }) as any });
        mapInstance.current?.addSource(measurementSourceId, { type: 'geojson', data: getMeasurementGeoJSON() as any });
        mapInstance.current?.addSource(drawSourceId, { type: 'geojson', data: getDrawGeoJSON() as any });
        
        mapInstance.current?.addLayer({ id: 'measure-lines', type: 'line', source: measurementSourceId, paint: { 'line-color': '#ffea00', 'line-width': 2, 'line-dasharray': [2, 2] } });
        mapInstance.current?.addLayer({ id: 'measure-points', type: 'circle', source: measurementSourceId, paint: { 'circle-radius': 4, 'circle-color': '#ffea00' } });
        mapInstance.current?.addLayer({ id: 'draw-polygon-fill', type: 'fill', source: drawSourceId, paint: { 'fill-color': '#00ff00', 'fill-opacity': 0.2 } });
        mapInstance.current?.addLayer({ id: 'draw-polygon-stroke', type: 'line', source: drawSourceId, paint: { 'line-color': '#00ff00', 'line-width': 2 } });
        mapInstance.current?.addLayer({ id: 'draw-lines', type: 'line', source: drawSourceId, paint: { 'line-color': '#00ff00', 'line-width': 2, 'line-dasharray': [2, 2] } });

        addDataLayers(mapInstance.current!, layers);
      }
    });
  }, [basemap]);

  // Sync GeoJSON Data
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current) return;
    const aiSource = mapInstance.current.getSource('ai-data') as maplibregl.GeoJSONSource;
    if (aiSource) aiSource.setData((aiGeoJson || { type: 'FeatureCollection', features: [] }) as any);
    
    const osmSource = mapInstance.current.getSource('osm-data') as maplibregl.GeoJSONSource;
    if (osmSource) osmSource.setData((osmGeoJson || { type: 'FeatureCollection', features: [] }) as any);
  }, [aiGeoJson, osmGeoJson, mapLoaded]);

  // Sync Bounds
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current || !bounds || bounds.length !== 4) return;
    mapInstance.current.fitBounds([
      [bounds[0], bounds[1]],
      [bounds[2], bounds[3]]
    ], { padding: 40 });
  }, [bounds, mapLoaded]);

  // Sync Layers config (opacity, visibility)
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current) return;
    const map = mapInstance.current;
    
    layers.forEach(layerConfig => {
      // Find all maplibre layers that correspond to this conceptual layer
      const mapLayerIds = drawLayerIds.current.filter(id => id.startsWith(`${layerConfig.id}-`));
      mapLayerIds.forEach(id => {
        const layer = map.getLayer(id);
        if (layer) {
          map.setLayoutProperty(id, 'visibility', layerConfig.visible ? 'visible' : 'none');
          if (layer.type === 'fill') {
            map.setPaintProperty(id, 'fill-opacity', layerConfig.opacity * 0.4);
          } else if (layer.type === 'line') {
            map.setPaintProperty(id, 'line-opacity', layerConfig.opacity);
          } else if (layer.type === 'circle') {
            map.setPaintProperty(id, 'circle-opacity', layerConfig.opacity);
          }
        }
      });
    });
  }, [layers, mapLoaded]);

  const addDataLayers = (map: maplibregl.Map, layerConfigs: MapLayerConfig[]) => {
    // Clear old tracked layers
    drawLayerIds.current.forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
    drawLayerIds.current = [];

    const addLayerGroup = (config: MapLayerConfig, source: string) => {
      const isOSM = source === 'osm-data';
      const color = config.color || CLASS_COLORS[config.id] || '#ffffff';
      
      const filterMatch = ['==', isOSM ? ['get', 'category'] : ['get', 'class_name'], config.id];

      // Fill
      const fillId = `${config.id}-fill`;
      map.addLayer({
        id: fillId,
        type: 'fill',
        source: source,
        filter: ['all', filterMatch, ['==', ['geometry-type'], 'Polygon']] as any,
        paint: {
          'fill-color': color,
          'fill-opacity': config.visible ? config.opacity * 0.4 : 0
        },
        layout: { 'visibility': config.visible ? 'visible' : 'none' }
      });
      drawLayerIds.current.push(fillId);

      // Line
      const lineId = `${config.id}-line`;
      map.addLayer({
        id: lineId,
        type: 'line',
        source: source,
        filter: ['all', filterMatch, ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'LineString']]] as any,
        paint: {
          'line-color': color,
          'line-width': isOSM ? 1 : 2,
          'line-opacity': config.visible ? config.opacity : 0
        },
        layout: { 'visibility': config.visible ? 'visible' : 'none' }
      });
      drawLayerIds.current.push(lineId);

      // Point
      const pointId = `${config.id}-point`;
      map.addLayer({
        id: pointId,
        type: 'circle',
        source: source,
        filter: ['all', filterMatch, ['==', ['geometry-type'], 'Point']] as any,
        paint: {
          'circle-color': color,
          'circle-radius': 5,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#000',
          'circle-opacity': config.visible ? config.opacity : 0
        },
        layout: { 'visibility': config.visible ? 'visible' : 'none' }
      });
      drawLayerIds.current.push(pointId);
    };

    layerConfigs.forEach(l => {
      if (['road', 'building', 'water', 'tree_cover', 'barren_land', 'agriculture'].includes(l.id)) {
        addLayerGroup(l, 'ai-data');
      } else {
        addLayerGroup(l, 'osm-data');
      }
    });
  };

  // Interactions based on mode
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current) return;
    const map = mapInstance.current;

    const onMapClick = (e: maplibregl.MapMouseEvent) => {
      if (mode === 'select') {
        const features = map.queryRenderedFeatures(e.point, { layers: drawLayerIds.current });
        if (features.length > 0) {
          onFeatureSelect(features[0]);
        } else {
          onFeatureSelect(null);
        }
      } else if (mode === 'distance' || mode === 'area') {
        const coords = [e.lngLat.lng, e.lngLat.lat];
        setCurrentDrawCoords(prev => {
          const updated = [...prev, coords];
          updateDrawSource(updated);
          return updated;
        });
      } else if (mode === 'draw') {
        const coords = [e.lngLat.lng, e.lngLat.lat];
        setCurrentDrawCoords(prev => {
          const updated = [...prev, coords];
          updateDrawSource(updated);
          return updated;
        });
      }
    };

    const onDoubleClick = (e: maplibregl.MapMouseEvent) => {
      if (mode === 'distance' || mode === 'area' || mode === 'draw') {
        e.preventDefault(); // stop zoom
        
        setCurrentDrawCoords(prev => {
          if (prev.length > 0) {
            if (mode === 'distance') {
               const line = turf.lineString(prev);
               const dist = turf.length(line, { units: 'kilometers' });
               setDrawResult({ text: `${dist.toFixed(2)} km`, type: 'Distance', coords: prev });
            } else if (mode === 'area' || mode === 'draw') {
               if (prev.length >= 3) {
                 const polyCoords = [...prev, prev[0]]; // Close polygon
                 const poly = turf.polygon([polyCoords]);
                 const area = turf.area(poly);
                 const text = area < 10000 ? `${area.toFixed(2)} m²` : `${(area / 10000).toFixed(2)} ha`;
                 setDrawResult({ text, type: 'Area', coords: prev });
               }
            }
            
            // Clear current, we could store it in drawFeatures if we want it persistent. 
            // For now, let's just clear it after showing the alert.
            updateDrawSource([]);
          }
          return [];
        });
      }
    };

    const onMouseMove = (e: maplibregl.MapMouseEvent) => {
      if ((mode === 'distance' || mode === 'area' || mode === 'draw') && currentDrawCoords.length > 0) {
        const coords = [e.lngLat.lng, e.lngLat.lat];
        updateDrawSource([...currentDrawCoords, coords]);
      }
    };

    map.on('click', onMapClick);
    map.on('dblclick', onDoubleClick);
    map.on('mousemove', onMouseMove);

    return () => {
      map.off('click', onMapClick);
      map.off('dblclick', onDoubleClick);
      map.off('mousemove', onMouseMove);
    };
  }, [mode, currentDrawCoords, mapLoaded]);

  // Mode change reset
  useEffect(() => {
    setCurrentDrawCoords([]);
    updateDrawSource([]);
    setDrawResult(null);
  }, [mode]);

  const getMeasurementGeoJSON = () => {
    if (currentDrawCoords.length === 0) return { type: 'FeatureCollection', features: [] };
    const points = currentDrawCoords.map(c => turf.point(c));
    const line = currentDrawCoords.length > 1 ? turf.lineString(currentDrawCoords) : null;
    
    const features: any[] = [...points];
    if (line) features.push(line);
    return turf.featureCollection(features as any);
  };

  const getDrawGeoJSON = () => {
    if (mode === 'distance') return getMeasurementGeoJSON();
    
    if (currentDrawCoords.length === 0) return { type: 'FeatureCollection', features: [] };
    const points = currentDrawCoords.map(c => turf.point(c));
    
    let poly: any = null;
    let line = currentDrawCoords.length > 1 ? turf.lineString(currentDrawCoords) : null;
    
    if (currentDrawCoords.length >= 3) {
       poly = turf.polygon([[...currentDrawCoords, currentDrawCoords[0]]]);
    }
    
    const features: any[] = [...points];
    if (poly) features.push(poly);
    else if (line) features.push(line);

    return turf.featureCollection(features as any);
  };

  const updateDrawSource = (coords: any[]) => {
    if (!mapLoaded || !mapInstance.current) return;
    
    const srcId = mode === 'distance' ? measurementSourceId : drawSourceId;
    const otherSrcId = mode === 'distance' ? drawSourceId : measurementSourceId;
    
    const source = mapInstance.current.getSource(srcId) as maplibregl.GeoJSONSource;
    const otherSource = mapInstance.current.getSource(otherSrcId) as maplibregl.GeoJSONSource;
    
    if (source) {
       const points = coords.map(c => turf.point(c));
       let geomFeat: any = null;
       
       if (coords.length > 1) {
         if (mode === 'distance') geomFeat = turf.lineString(coords);
         else {
            if (coords.length >= 3) geomFeat = turf.polygon([[...coords, coords[0]]]);
            else geomFeat = turf.lineString(coords);
         }
       }
       
       source.setData(turf.featureCollection([...points, ...(geomFeat ? [geomFeat] : [])] as any));
    }
    if (otherSource) otherSource.setData(turf.featureCollection([]));
  };


  const handleExportDraw = () => {
     if (!drawResult) return;
     const feat = getDrawGeoJSON();
     const blob = new Blob([JSON.stringify(feat, null, 2)], { type: 'application/json' });
     const url = URL.createObjectURL(blob);
     const a = document.createElement('a');
     a.href = url;
     a.download = `urbansense_measurement.geojson`;
     a.click();
     URL.revokeObjectURL(url);
  };

  const handleClearDraw = () => {
     setCurrentDrawCoords([]);
     updateDrawSource([]);
     setDrawResult(null);
     if (onClearDraw) onClearDraw();
  };

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full bg-slate-900" />
      
      {drawResult && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl z-10 flex items-center gap-4">
           <div>
              <div className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">{drawResult.type}</div>
              <div className="text-xl font-bold text-emerald-400">{drawResult.text}</div>
           </div>
           <div className="flex gap-2 border-l border-slate-700 pl-4">
             <button onClick={handleExportDraw} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs font-medium transition-colors">Export</button>
             <button onClick={handleClearDraw} className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-xs font-medium transition-colors">Clear</button>
           </div>
        </div>
      )}
    </div>
  );
});
