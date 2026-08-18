import React from 'react';
import { 
  ZoomIn, ZoomOut, Maximize2, Crosshair, 
  MapPin, MousePointer2, Ruler, Square, 
  Download, SplitSquareVertical 
} from 'lucide-react';

interface MapToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetView: () => void;
  onToggleFullscreen: () => void;
  mode: 'select' | 'draw' | 'distance' | 'area' | 'compare';
  setMode: (mode: 'select' | 'draw' | 'distance' | 'area' | 'compare') => void;
  onExport: () => void;
}

export const MapToolbar: React.FC<MapToolbarProps> = ({
  onZoomIn, onZoomOut, onResetView, onToggleFullscreen,
  mode, setMode, onExport
}) => {
  return (
    <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
      {/* Navigation Controls */}
      <div className="bg-[#1e293b] rounded-lg shadow-lg border border-slate-700 flex flex-col p-1">
        <button onClick={onZoomIn} className="p-2 hover:bg-slate-700 rounded text-slate-300 transition-colors" title="Zoom In">
          <ZoomIn size={18} />
        </button>
        <button onClick={onZoomOut} className="p-2 hover:bg-slate-700 rounded text-slate-300 transition-colors" title="Zoom Out">
          <ZoomOut size={18} />
        </button>
        <button onClick={onResetView} className="p-2 hover:bg-slate-700 rounded text-slate-300 transition-colors" title="Reset View">
          <Crosshair size={18} />
        </button>
        <button onClick={onToggleFullscreen} className="p-2 hover:bg-slate-700 rounded text-slate-300 transition-colors" title="Toggle Fullscreen">
          <Maximize2 size={18} />
        </button>
      </div>

      {/* Tool Modes */}
      <div className="bg-[#1e293b] rounded-lg shadow-lg border border-slate-700 flex flex-col p-1 mt-2">
        <button 
          onClick={() => setMode('select')} 
          className={`p-2 rounded transition-colors ${mode === 'select' ? 'bg-blue-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`} 
          title="Select Feature"
        >
          <MousePointer2 size={18} />
        </button>
        <button 
          onClick={() => setMode('distance')} 
          className={`p-2 rounded transition-colors ${mode === 'distance' ? 'bg-blue-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`} 
          title="Measure Distance"
        >
          <Ruler size={18} />
        </button>
        <button 
          onClick={() => setMode('area')} 
          className={`p-2 rounded transition-colors ${mode === 'area' ? 'bg-blue-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`} 
          title="Measure Area"
        >
          <Square size={18} />
        </button>
        <button 
          onClick={() => setMode('draw')} 
          className={`p-2 rounded transition-colors ${mode === 'draw' ? 'bg-blue-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`} 
          title="Draw Polygon"
        >
          <MapPin size={18} />
        </button>
        <button 
          onClick={() => setMode('compare')} 
          className={`p-2 rounded transition-colors ${mode === 'compare' ? 'bg-blue-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`} 
          title="Compare Mode"
        >
          <SplitSquareVertical size={18} />
        </button>
      </div>

      {/* Actions */}
      <div className="bg-[#1e293b] rounded-lg shadow-lg border border-slate-700 flex flex-col p-1 mt-2">
        <button onClick={onExport} className="p-2 hover:bg-slate-700 rounded text-slate-300 transition-colors" title="Export GeoJSON">
          <Download size={18} />
        </button>
      </div>
    </div>
  );
};
