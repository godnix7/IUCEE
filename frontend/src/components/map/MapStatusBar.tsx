import React from 'react';
import type { ImageryAnalysis } from '../../types';

interface MapStatusBarProps {
  analysis: ImageryAnalysis | null;
  aiFeatureCount: number;
  osmFeatureCount: number;
  osmStatus: string;
}

export const MapStatusBar: React.FC<MapStatusBarProps> = ({
  analysis, aiFeatureCount, osmFeatureCount, osmStatus
}) => {
  return (
    <div className="h-8 bg-[#111827] border-t border-slate-800 flex items-center justify-between px-4 text-xs z-20 shrink-0">
      <div className="flex items-center gap-4 text-slate-400">
        <div>Analysis: <span className="text-slate-200">{analysis ? analysis.filename : 'None selected'}</span></div>
        <div>CRS: <span className="text-slate-200">EPSG:4326</span></div>
      </div>
      <div className="flex items-center gap-4 text-slate-400">
        <div>AI Features: <span className="text-slate-200">{analysis ? aiFeatureCount : 0}</span></div>
        <div className="flex items-center gap-1.5">
          OSM Enrichment: 
          {osmStatus === 'completed' && <span className="text-emerald-400">Completed ({osmFeatureCount})</span>}
          {osmStatus === 'processing' && <span className="text-blue-400">Processing...</span>}
          {osmStatus === 'partial' && <span className="text-yellow-400">Partial ({osmFeatureCount})</span>}
          {osmStatus === 'failed' && <span className="text-red-400">Failed</span>}
          {(!osmStatus || osmStatus === 'pending') && <span className="text-slate-500">Not run</span>}
        </div>
      </div>
    </div>
  );
};
