import React from 'react';

export const CLASS_COLORS: Record<string, string> = {
  // AI Classes
  road: '#3b82f6',
  building: '#ef4444',
  water: '#06b6d4',
  tree_cover: '#22c55e',
  barren_land: '#f97316',
  agriculture: '#eab308',
  // OSM Classes
  hospital: '#ec4899',
  school: '#a855f7',
  police: '#6366f1',
  fire_station: '#ea580c',
};

export const CLASS_LABELS: Record<string, string> = {
  road: 'Roads',
  building: 'Buildings',
  water: 'Water',
  tree_cover: 'Tree Cover',
  barren_land: 'Barren Land',
  agriculture: 'Agriculture',
  hospital: 'Hospitals',
  school: 'Schools',
  police: 'Police',
  fire_station: 'Fire Stations',
};

export const MapLegend: React.FC = () => {
  return (
    <div className="absolute bottom-6 right-4 z-10 bg-[#1e293b] border border-slate-700 rounded-lg shadow-xl p-4 w-48 text-sm">
      <div className="mb-3">
        <h4 className="text-slate-400 font-semibold text-xs tracking-wider mb-2">AI / COMPUTER VISION</h4>
        <div className="space-y-1.5">
          {['road', 'building', 'water', 'tree_cover', 'barren_land', 'agriculture'].map(cls => (
            <div key={cls} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: CLASS_COLORS[cls] }} />
              <span className="text-slate-200">{CLASS_LABELS[cls]}</span>
            </div>
          ))}
        </div>
      </div>
      
      <div className="pt-2 border-t border-slate-700">
        <h4 className="text-slate-400 font-semibold text-xs tracking-wider mb-2">OPENSTREETMAP / GIS</h4>
        <div className="space-y-1.5">
          {['hospital', 'school', 'police', 'fire_station'].map(cls => (
            <div key={cls} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border border-slate-900" style={{ backgroundColor: CLASS_COLORS[cls] }} />
              <span className="text-slate-200">{CLASS_LABELS[cls]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
