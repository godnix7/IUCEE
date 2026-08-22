import React from 'react';
import { Eye, EyeOff, Crosshair } from 'lucide-react';
import { CLASS_COLORS, CLASS_LABELS } from '../map/MapLegend';

export interface ReviewFeature {
  id: number;
  class_name: string;
  source?: string;
  confidence?: number;
  area_sq_meters?: number;
  feature_count?: number;
  model_name?: string;
  model_version?: string;
  coverage_pct?: number;
}

interface Props {
  features: ReviewFeature[];
  visible: Record<string, boolean>;
  selectedId: number | null;
  onToggleVisible: (className: string) => void;
  onIsolate: (className: string) => void;
  onShowAll: () => void;
  onHideAll: () => void;
  onSelect: (id: number) => void;
  onHoverClass?: (className: string | null) => void;
}

const fmtArea = (m2?: number) => {
  if (!m2 || m2 <= 0) return null;
  return m2 < 10000 ? `${m2.toFixed(0)} m²` : `${(m2 / 10000).toFixed(2)} ha`;
};

export const DetectionReviewPanel: React.FC<Props> = ({
  features, visible, selectedId, onToggleVisible, onIsolate, onShowAll, onHideAll, onSelect, onHoverClass,
}) => {
  return (
    <div className="w-80 shrink-0 border-l border-slate-800 bg-[#0e1420] flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-200 tracking-wide">DETECTED CLASSES</h3>
        <div className="flex gap-1.5 text-[10px]">
          <button onClick={onShowAll} className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300">Show all</button>
          <button onClick={onHideAll} className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300">Hide all</button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {features.length === 0 && (
          <div className="text-xs text-slate-500 p-4 text-center">No AI detections are available for this analysis.</div>
        )}

        {features.map((f) => {
          const color = CLASS_COLORS[f.class_name] || '#94a3b8';
          const isVisible = visible[f.class_name] !== false;
          const isSel = selectedId === f.id;
          const area = fmtArea(f.area_sq_meters);
          return (
            <div
              key={f.id}
              onClick={() => onSelect(f.id)}
              onMouseEnter={() => onHoverClass?.(f.class_name)}
              onMouseLeave={() => onHoverClass?.(null)}
              className={`rounded-xl border p-2.5 cursor-pointer transition-colors ${
                isSel ? 'bg-blue-500/5 border-blue-500/50' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                <span className="text-xs font-semibold text-slate-100 flex-1 truncate">
                  {CLASS_LABELS[f.class_name] || f.class_name}
                </span>
                {typeof f.coverage_pct === 'number' && (
                  <span className="text-[11px] text-slate-300 tabular-nums">{f.coverage_pct}%</span>
                )}
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => onToggleVisible(f.class_name)} title={isVisible ? 'Hide' : 'Show'}
                    className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800">
                    {isVisible ? <Eye size={13} /> : <EyeOff size={13} />}
                  </button>
                  <button onClick={() => onIsolate(f.class_name)} title="Isolate"
                    className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800">
                    <Crosshair size={13} />
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-400 tabular-nums pl-5">
                {typeof f.coverage_pct === 'number'
                  ? <span>{(f.feature_count ?? 0).toLocaleString()} px</span>
                  : <span>{f.feature_count ?? 0} features</span>}
                {area && <span>{area}</span>}
                {typeof f.confidence === 'number' && <span>conf {(f.confidence * 100).toFixed(0)}%</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
