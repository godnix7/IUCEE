import React from 'react';
import { ArrowLeft, Cpu, Layers } from 'lucide-react';
import type { ImageryAnalysis } from '../../types';

interface Props {
  analysis: ImageryAnalysis;
  modelName?: string | null;
  classCount: number;
  onBack: () => void;
}

const MODE_LABEL: Record<string, string> = {
  detection: 'Object Detection',
  scene_segmentation: 'Scene Segmentation',
  segmentation: 'Land-cover Segmentation',
};

export const ReviewSummaryBar: React.FC<Props> = ({ analysis, modelName, classCount, onBack }) => {
  const mode = analysis.analysis_mode || 'segmentation';
  return (
    <div className="bg-[#111827] border-b border-slate-800 px-5 py-3 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={onBack} className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 shrink-0" title="Back">
          <ArrowLeft size={18} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-sm font-semibold text-white truncate">
            Review AI Detections — <span className="text-slate-300">{analysis.filename}</span>
          </h1>
          <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-0.5 flex-wrap">
            <span className="flex items-center gap-1"><Cpu size={11} /> {modelName || '—'}</span>
            <span className="flex items-center gap-1"><Layers size={11} /> {MODE_LABEL[mode] || mode}</span>
            <span className={analysis.status === 'completed' ? 'text-emerald-400' : 'text-blue-400'}>{analysis.status}</span>
            <span>{classCount} classes</span>
          </div>
        </div>
      </div>
    </div>
  );
};
