import React from 'react';
import { Layers, Eye, EyeOff } from 'lucide-react';
import type { MapLayerConfig } from '../../types';
import { CLASS_COLORS, CLASS_LABELS } from './MapLegend';

interface LayerPanelProps {
  basemap: 'satellite' | 'streets' | 'terrain';
  setBasemap: (b: 'satellite' | 'streets' | 'terrain') => void;
  layers: MapLayerConfig[];
  onToggleLayer: (id: string) => void;
  onChangeOpacity: (id: string, opacity: number) => void;
  onZoomLayer: (id: string) => void;
}

export const LayerPanel: React.FC<LayerPanelProps> = ({
  basemap, setBasemap, layers, onToggleLayer, onChangeOpacity, onZoomLayer
}) => {
  const aiLayers = layers.filter(l => ['road', 'building', 'water', 'tree_cover', 'barren_land', 'agriculture'].includes(l.id));
  const osmLayers = layers.filter(l => ['hospital', 'school', 'police', 'fire_station'].includes(l.id));

  const renderLayerGroup = (title: string, groupLayers: MapLayerConfig[]) => (
    <div className="mb-4">
      <h4 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider px-1">{title}</h4>
      <div className="space-y-1">
        {groupLayers.map(layer => (
          <div key={layer.id} className="bg-slate-800/50 rounded p-2 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: CLASS_COLORS[layer.id] || '#ccc' }} />
                <span className="text-sm font-medium text-slate-200">
                  {CLASS_LABELS[layer.id] || layer.label} 
                  <span className="ml-1 text-slate-500 text-xs">({layer.count})</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => layer.count > 0 && onZoomLayer(layer.id)}
                  className={`text-slate-400 hover:text-white transition-colors ${layer.count === 0 ? 'opacity-30 cursor-not-allowed' : ''}`}
                  title="Zoom to Layer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
                </button>
                <button 
                  onClick={() => onToggleLayer(layer.id)}
                  className="text-slate-400 hover:text-white transition-colors"
                >
                  {layer.visible ? <Eye size={14} /> : <EyeOff size={14} />}
                </button>
              </div>
            </div>
            {layer.count === 0 && (
               <div className="text-[10px] text-slate-500 italic mt-1 uppercase">No features available</div>
            )}
            {layer.visible && layer.count > 0 && (
              <input 
                type="range" 
                min="0" max="1" step="0.1" 
                value={layer.opacity}
                onChange={(e) => onChangeOpacity(layer.id, parseFloat(e.target.value))}
                className="w-full h-1 bg-slate-700 rounded appearance-none cursor-pointer mt-1"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="w-64 bg-[#111827] border-r border-slate-800 flex flex-col h-full overflow-y-auto">
      <div className="p-4 border-b border-slate-800 flex items-center gap-2">
        <Layers className="text-blue-400" size={18} />
        <h3 className="font-semibold text-slate-100">Map Layers</h3>
      </div>
      
      <div className="p-4 flex-1">
        <div className="mb-6">
          <h4 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider px-1">BASE MAPS</h4>
          <div className="space-y-1">
            {['satellite', 'streets', 'terrain'].map(b => (
              <label key={b} className="flex items-center gap-2 p-2 hover:bg-slate-800/50 rounded cursor-pointer">
                <input 
                  type="radio" 
                  name="basemap" 
                  checked={basemap === b}
                  onChange={() => setBasemap(b as any)}
                  className="accent-blue-500"
                />
                <span className="text-sm text-slate-200 capitalize">{b}</span>
              </label>
            ))}
          </div>
        </div>

        {renderLayerGroup('AI LAYERS', aiLayers)}
        {renderLayerGroup('OPENSTREETMAP', osmLayers)}
      </div>
    </div>
  );
};
