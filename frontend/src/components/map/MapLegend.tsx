import React from 'react';
import type { MapLayerConfig } from '../../types';

export const CLASS_COLORS: Record<string, string> = {
  // AI Classes (nadir land-cover)
  road: '#3b82f6',
  building: '#ef4444',
  water: '#06b6d4',
  tree_cover: '#22c55e',
  barren_land: '#f97316',
  agriculture: '#eab308',
  // ADE20K scene-segmentation extras (oblique / drone)
  sidewalk: '#eab308',
  grass: '#84cc16',
  vehicle: '#3b82f6',
  person: '#ec4899',
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
  sidewalk: 'Sidewalk',
  grass: 'Grass',
  vehicle: 'Vehicles',
  person: 'People',
  hospital: 'Hospitals',
  school: 'Schools',
  police: 'Police',
  fire_station: 'Fire Stations',
};

const AI_CLASSES = ['road', 'building', 'water', 'tree_cover', 'barren_land', 'agriculture'];
const OSM_CLASSES = ['hospital', 'school', 'police', 'fire_station'];

interface LegendProps {
  /** When provided, the legend reflects real per-class feature counts and hides empty sections. */
  layers?: MapLayerConfig[];
}

export const MapLegend: React.FC<LegendProps> = ({ layers }) => {
  const countFor = (id: string): number | null =>
    layers ? (layers.find((l) => l.id === id)?.count ?? 0) : null;

  const renderSection = (title: string, classes: string[], shape: 'sq' | 'circle') => {
    const rows = classes
      .map((cls) => ({ cls, count: countFor(cls) }))
      // When counts are known, only show classes that actually have features
      .filter((r) => (layers ? (r.count ?? 0) > 0 : true));

    return (
      <div className="pointer-events-auto">
        <h4 className="text-slate-400 font-semibold text-xs tracking-wider mb-2">{title}</h4>
        {rows.length === 0 ? (
          <div className="text-[11px] text-slate-500 italic mb-1">No features available</div>
        ) : (
          <div className="space-y-1.5">
            {rows.map(({ cls, count }) => (
              <div key={cls} className="flex items-center gap-2">
                <span
                  className={`w-3 h-3 ${shape === 'circle' ? 'rounded-full border border-slate-900' : 'rounded-sm'}`}
                  style={{ backgroundColor: CLASS_COLORS[cls] }}
                />
                <span className="text-slate-200 flex-1">{CLASS_LABELS[cls]}</span>
                {count !== null && <span className="text-slate-500 tabular-nums text-[11px]">{count}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="absolute bottom-6 left-4 z-10 bg-[#1e293b] border border-slate-700 rounded-lg shadow-xl p-4 w-52 text-sm pointer-events-none">
      <div className="mb-3">{renderSection('AI / COMPUTER VISION', AI_CLASSES, 'sq')}</div>
      <div className="pt-2 border-t border-slate-700">{renderSection('OPENSTREETMAP / GIS', OSM_CLASSES, 'circle')}</div>
    </div>
  );
};
