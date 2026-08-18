import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { MapLayerConfig } from '../../types';
import { MapView } from './MapView';

interface MapCompareProps {
  aiGeoJson: any;
  osmGeoJson: any;
  layers: MapLayerConfig[];
  basemap: 'satellite' | 'streets' | 'terrain';
  bounds?: number[];
  onFeatureSelect: (feature: any) => void;
}

export const MapCompare: React.FC<MapCompareProps> = ({
  aiGeoJson, osmGeoJson, layers, basemap, bounds, onFeatureSelect
}) => {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const leftMapRef = useRef<maplibregl.Map | null>(null);
  const rightMapRef = useRef<maplibregl.Map | null>(null);
  const isSyncing = useRef(false);

  useEffect(() => {
    if (!leftMapRef.current || !rightMapRef.current) return;
    
    const leftMap = leftMapRef.current;
    const rightMap = rightMapRef.current;

    const syncMaps = (source: maplibregl.Map, target: maplibregl.Map) => {
       if (isSyncing.current) return;
       isSyncing.current = true;
       target.jumpTo({
          center: source.getCenter(),
          zoom: source.getZoom(),
          bearing: source.getBearing(),
          pitch: source.getPitch()
       });
       isSyncing.current = false;
    };

    const onLeftMove = () => syncMaps(leftMap, rightMap);
    const onRightMove = () => syncMaps(rightMap, leftMap);

    leftMap.on('move', onLeftMove);
    rightMap.on('move', onRightMove);

    return () => {
       leftMap.off('move', onLeftMove);
       rightMap.off('move', onRightMove);
    };
  }, []);

  const handleMouseMove = (e: React.MouseEvent | MouseEvent) => {
    if (e.buttons !== 1 || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pos = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    setSliderPos(pos);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pos = Math.max(0, Math.min(100, ((e.touches[0].clientX - rect.left) / rect.width) * 100));
    setSliderPos(pos);
  };

  useEffect(() => {
     const onMouseUp = () => document.body.style.userSelect = 'auto';
     window.addEventListener('mouseup', onMouseUp);
     return () => window.removeEventListener('mouseup', onMouseUp);
  }, []);

  return (
    <div 
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none"
    >
      {/* Left Map: Original Imagery (No layers) */}
      <div className="absolute inset-0">
        <MapView 
          ref={leftMapRef}
          aiGeoJson={null}
          osmGeoJson={null}
          layers={[]} // Empty layers so it's just the basemap
          basemap={basemap}
          mode="select"
          onFeatureSelect={() => {}}
          bounds={bounds}
        />
      </div>

      {/* Right Map: UrbanSense Layers */}
      <div 
        className="absolute inset-0 border-l border-slate-500 shadow-2xl" 
        style={{ clipPath: `inset(0 0 0 ${sliderPos}%)` }}
      >
        <MapView 
          ref={rightMapRef}
          aiGeoJson={aiGeoJson}
          osmGeoJson={osmGeoJson}
          layers={layers}
          basemap={basemap}
          mode="select"
          onFeatureSelect={onFeatureSelect}
          bounds={bounds}
        />
      </div>

      {/* Slider Handle */}
      <div 
        className="absolute top-0 bottom-0 w-1 bg-white cursor-ew-resize hover:w-1.5 transition-all z-20 flex flex-col justify-center items-center group"
        style={{ left: `${sliderPos}%`, transform: 'translateX(-50%)' }}
        onMouseDown={(e) => {
           e.preventDefault();
           document.body.style.userSelect = 'none';
           document.addEventListener('mousemove', handleMouseMove);
           document.addEventListener('mouseup', () => document.removeEventListener('mousemove', handleMouseMove), { once: true });
        }}
        onTouchMove={handleTouchMove}
      >
        <div className="w-8 h-8 bg-white text-slate-800 shadow-xl rounded-full flex items-center justify-center pointer-events-none group-hover:scale-110 transition-transform">
           <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
           <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6"/></svg>
        </div>
      </div>
    </div>
  );
};
