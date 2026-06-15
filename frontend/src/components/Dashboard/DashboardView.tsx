// No unused imports

import { useState, useEffect } from 'react';
import { Play, Pause, Square, Activity, Info, Check } from 'lucide-react';
import { api } from '../../api';

export default function DashboardView({ project, stats, onStatsUpdate }: { project: any, stats: any, onStatsUpdate: () => void }) {
  const [feedback, setFeedback] = useState<string | null>(null);
  if (!project) return <div className="p-8">No project selected</div>;
  if (!stats) return <div className="p-8 text-textMuted">Loading stats from database...</div>;

  const progress = stats.total_images > 0 
    ? Math.round((stats.processed_images / stats.total_images) * 100) 
    : 0;

  const handleAction = async (action: 'auto-label' | 'pause' | 'resume' | 'stop') => {
    try {
      if (action === 'auto-label') {
        setFeedback("Processing Started");
        await api.labeling.autoLabelAll(project.id);
      }
      if (action === 'pause') {
        setFeedback("Processing Paused");
        await api.labeling.pause(project.id);
      }
      if (action === 'resume') {
        setFeedback("Processing Resumed");
        await api.labeling.resume(project.id);
      }
      if (action === 'stop') {
        setFeedback("Queue Stopped");
        await api.labeling.stop(project.id);
      }
      setTimeout(() => setFeedback(null), 3000);
      onStatsUpdate();
    } catch (e) {
      console.error(e);
      setFeedback("Action Failed");
    }
  };

  // State calculations
  const state = stats.engine_state || 'STOPPED';
  const isRunning = state === 'RUNNING';
  const isPaused = state === 'PAUSED';
  const isStopped = state === 'STOPPED';

  const etaMinutes = stats.hardware?.images_per_minute && stats.remaining_images 
    ? Math.round(stats.remaining_images / stats.hardware.images_per_minute) 
    : 0;

  return (
    <div className="flex-1 p-8 overflow-y-auto">
      <div className="flex flex-col xl:flex-row gap-6 mb-8">
        
        {/* Controls Panel */}
        <div className="glass-panel p-6 flex-1 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <h3 className="text-xl font-bold mb-6 flex items-center gap-3 relative z-10">
            <div className={`p-2 rounded-lg ${isRunning ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : isPaused ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-800 text-slate-400'}`}>
              <Activity size={22} className={isRunning ? 'animate-pulse' : ''} />
            </div>
            Processing Controls
          </h3>
          
          <div className="flex flex-wrap gap-4 mb-4 relative z-10">
            <button 
              onClick={() => handleAction('auto-label')} 
              disabled={!isStopped} 
              title="Start Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-emerald-500/20 to-emerald-600/20 text-emerald-400 hover:from-emerald-500/30 hover:to-emerald-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-emerald-500/30 hover:border-emerald-400/50 hover:shadow-[0_0_20px_rgba(16,185,129,0.2)]"
            >
              <Play size={20} /> Start
            </button>
            <button 
              onClick={() => handleAction('pause')} 
              disabled={!isRunning} 
              title="Pause Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-amber-500/20 to-amber-600/20 text-amber-400 hover:from-amber-500/30 hover:to-amber-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-amber-500/30 hover:border-amber-400/50 hover:shadow-[0_0_20px_rgba(245,158,11,0.2)]"
            >
              <Pause size={20} /> Pause
            </button>
            <button 
              onClick={() => handleAction('resume')} 
              disabled={!isPaused} 
              title="Resume Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-blue-500/20 to-blue-600/20 text-blue-400 hover:from-blue-500/30 hover:to-blue-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-blue-500/30 hover:border-blue-400/50 hover:shadow-[0_0_20px_rgba(59,130,246,0.2)]"
            >
              <Play size={20} /> Resume
            </button>
            <button 
              onClick={() => handleAction('stop')} 
              disabled={isStopped} 
              title="Stop Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-red-500/20 to-red-600/20 text-red-400 hover:from-red-500/30 hover:to-red-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-red-500/30 hover:border-red-400/50 hover:shadow-[0_0_20px_rgba(239,68,68,0.2)]"
            >
              <Square size={20} /> Stop
            </button>
          </div>

          {feedback && (
            <div className="absolute bottom-4 right-6 text-emerald-400 font-medium text-sm flex items-center gap-2 animate-in slide-in-from-bottom-2 fade-in">
              <Info size={16} /> {feedback}
            </div>
          )}
        </div>

        {/* Processing Information Panel */}
        <div className="glass-panel p-6 flex-1 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-bl from-accent/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <h3 className="text-xl font-bold mb-6 text-white relative z-10">Processing Stats</h3>
          <div className="grid grid-cols-2 gap-y-6 gap-x-8 text-sm relative z-10">
            <div className="flex flex-col">
              <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Engine Status</span>
              <span className={`text-base font-bold flex items-center gap-2 ${isRunning ? 'text-emerald-400' : isPaused ? 'text-amber-400' : 'text-slate-400'}`}>
                {isRunning && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>}
                {state === 'RUNNING' ? 'Running' : state === 'PAUSED' ? 'Paused' : 'Stopped'}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Processed</span>
              <span className="text-base font-semibold text-white">{stats.processed_images} / {stats.total_images}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Queue Size</span>
              <span className="text-base font-semibold text-white bg-white/10 px-3 py-1 rounded-md w-max">{stats.queue_size}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Estimated Time Remaining</span>
              <span className="text-base font-semibold text-white">{etaMinutes} minutes</span>
            </div>
          </div>
        </div>
      </div>

      {/* GPU Hardware Telemetry */}
      <div className="mb-8 glass-panel p-6 overflow-hidden relative group">
        <div className="absolute inset-0 bg-gradient-to-r from-secondary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
        <h3 className="text-xl font-bold mb-6 text-white relative z-10 flex items-center gap-2">
          <Activity size={20} className="text-secondary" />
          Hardware Telemetry
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-y-6 gap-x-8 text-sm relative z-10">
          <div className="flex flex-col">
            <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Compute Device</span>
            <span className="text-base font-bold text-white flex items-center gap-2">
              {stats.hardware?.device_name || 'CPU'}
              {stats.hardware?.device_type === 'cuda' && (
                <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">CUDA</span>
              )}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">GPU Utilization</span>
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold text-white">{stats.hardware?.gpu_utilization_pct || 0}%</span>
              <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-secondary transition-all duration-500" 
                  style={{ width: `${stats.hardware?.gpu_utilization_pct || 0}%` }}
                ></div>
              </div>
            </div>
          </div>
          <div className="flex flex-col">
            <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">VRAM Usage</span>
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold text-white">
                {stats.hardware?.vram_used_gb || 0} / {stats.hardware?.vram_total_gb || 0} <span className="text-xs text-textMuted">GB</span>
              </span>
              <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-accent transition-all duration-500" 
                  style={{ width: `${Math.min(100, ((stats.hardware?.vram_used_gb || 0) / (stats.hardware?.vram_total_gb || 1)) * 100)}%` }}
                ></div>
              </div>
            </div>
          </div>
          <div className="flex flex-col">
            <span className="text-textMuted mb-1 text-xs uppercase tracking-wider">Inference Speed</span>
            <span className="text-base font-semibold text-accent">
              {(stats.hardware?.images_per_minute / 60 || 0).toFixed(1)} <span className="text-xs text-textMuted">img/sec</span>
              <span className="ml-2 text-xs text-textMuted">({Math.round(stats.hardware?.avg_inference_ms || 0)} ms/img)</span>
            </span>
          </div>
        </div>
      </div>
      
      <div className="mb-8 glass-panel p-6">
        <div className="flex justify-between mb-2">
          <span className="text-textMuted">Overall Pipeline Progress</span>
          <span className="font-bold">{progress}%</span>
        </div>
        <div className="w-full bg-slate-900 rounded-full h-4 overflow-hidden border border-white/10">
          <div 
            className="bg-primary h-4 transition-all duration-500 ease-in-out relative" 
            style={{ width: `${progress}%` }}
          >
            <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
          </div>
        </div>
        <div className="flex justify-between mt-2 text-xs text-textMuted">
          <span>{stats.processed_images} processed</span>
          <span>{stats.remaining_images} remaining</span>
        </div>
      </div>

      {/* Hardware Telemetry Panel */}
      {stats.hardware && (
        <div className="mb-8 glass-panel p-6 border border-primary/20 bg-primary/5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-primary">Runtime Verification</h3>
            <div className={`px-3 py-1 rounded-full text-xs font-bold ${stats.hardware.device_type === 'cuda' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
              {stats.hardware.device_type === 'cuda' ? 'CUDA Active' : 'CPU Fallback'}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <div className="text-xs text-textMuted uppercase">Compute Device</div>
              <div className="font-semibold">{stats.hardware.device_name}</div>
            </div>
            <div>
              <div className="text-xs text-textMuted uppercase">GPU Utilization</div>
              <div className="font-semibold">{stats.hardware.gpu_utilization_pct}%</div>
            </div>
            <div>
              <div className="text-xs text-textMuted uppercase">VRAM Usage</div>
              <div className="font-semibold">{stats.hardware.vram_used_gb} / {stats.hardware.vram_total_gb} GB</div>
            </div>
            <div>
              <div className="text-xs text-textMuted uppercase">Images / Min</div>
              <div className="font-semibold">{stats.hardware.images_per_minute} IPM</div>
            </div>
            <div>
              <div className="text-xs text-textMuted uppercase">Avg Inference</div>
              <div className="font-semibold">{stats.hardware.avg_inference_ms} ms</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="Total Images" value={stats.total_images} color="text-white" />
        <StatCard title="LS Tasks Sent" value={stats.ls_tasks_sent || 0} color="text-blue-400" />
        <StatCard title="LS Tasks Reviewed" value={stats.ls_tasks_reviewed || 0} color="text-emerald-400" />
        <StatCard title="LS Tasks Corrected" value={stats.ls_tasks_corrected || 0} color="text-amber-400" />
        
        <StatCard title="LS Tasks Pending" value={stats.ls_tasks_pending || 0} color="text-orange-400" />
        <StatCard title="Images Processed" value={stats.processed_images} color="text-primary" />
        <StatCard title="Images Remaining" value={stats.remaining_images} color="text-accent" />
        <StatCard title="Avg Confidence" value={`${(stats.avg_confidence * 100).toFixed(1)}%`} color="text-secondary" />
      </div>

      <div className="glass-panel p-6">
        <h3 className="text-lg font-medium mb-4">Class Distribution</h3>
        {Object.keys(stats.class_distribution || {}).length === 0 ? (
          <p className="text-textMuted text-sm">No annotations yet</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(stats.class_distribution).map(([cls, count]: [string, any]) => {
              const maxCount = Math.max(...Object.values(stats.class_distribution as Record<string, number>));
              const percentage = (count / maxCount) * 100;
              return (
                <div key={cls} className="flex items-center gap-4">
                  <div className="w-24 text-sm font-medium truncate">{cls}</div>
                  <div className="flex-1 h-3 bg-slate-900 rounded-full overflow-hidden">
                    <div className="h-full bg-secondary rounded-full" style={{ width: `${percentage}%` }}></div>
                  </div>
                  <div className="w-12 text-right text-sm text-textMuted">{count}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bulk Cleanup Tools */}
      <BulkCleanupTools project={project} onStatsUpdate={onStatsUpdate} />
    </div>
  );
}

function BulkCleanupTools({ project, onStatsUpdate }: { project: any, onStatsUpdate: () => void }) {
  const [deleteSourceFiles, setDeleteSourceFiles] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleCleanup = async (target: string) => {
    setIsDeleting(true);
    try {
      await api.projects.cleanup(project.id, target, deleteSourceFiles);
      setConfirmAction(null);
      onStatsUpdate();
    } catch (err) {
      console.error(err);
      alert('Cleanup failed');
    } finally {
      setIsDeleting(false);
    }
  };

  const actionLabels: Record<string, string> = {
    processed: "Remove All Processed Images",
    reviewed: "Remove All Reviewed Images",
    accepted: "Remove All Accepted Images",
    rejected: "Remove All Rejected Images",
    completed_queue: "Clear Completed Queue",
    all: "Clear Entire Project"
  };

  return (
    <div className="mt-8 glass-panel p-6 border border-red-500/20 bg-red-500/5">
      <h3 className="text-lg font-bold text-red-400 mb-4">Danger Zone: Bulk Cleanup Tools</h3>
      
      <div className="mb-6">
        <label className="flex items-center gap-3 cursor-pointer group w-max">
          <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${deleteSourceFiles ? 'bg-red-500 border-red-500' : 'border-white/20 group-hover:border-white/40'}`}>
            {deleteSourceFiles && <Check size={14} className="text-white" />}
          </div>
          <input type="checkbox" className="hidden" checked={deleteSourceFiles} onChange={e => setDeleteSourceFiles(e.target.checked)} />
          <span className="text-sm font-medium text-textMuted group-hover:text-white transition-colors">Also Delete Source Files (.jpg, .png) from Disk</span>
        </label>
        {deleteSourceFiles && <p className="text-xs text-red-400 mt-2 ml-8">Warning: This cannot be undone. Source files will be permanently deleted.</p>}
      </div>

      <div className="flex flex-wrap gap-4">
        {Object.entries(actionLabels).map(([key, label]) => (
          <div key={key}>
            {confirmAction === key ? (
              <div className="flex items-center gap-2 animate-in fade-in zoom-in duration-200">
                <span className="text-sm font-medium text-red-400 mr-2">Are you sure?</span>
                <button disabled={isDeleting} onClick={() => handleCleanup(key)} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-medium transition-colors disabled:opacity-50">
                  {isDeleting ? 'Deleting...' : 'Yes, Delete'}
                </button>
                <button disabled={isDeleting} onClick={() => setConfirmAction(null)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm font-medium transition-colors disabled:opacity-50">
                  Cancel
                </button>
              </div>
            ) : (
              <button 
                onClick={() => setConfirmAction(key)}
                className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded text-sm font-medium transition-colors"
              >
                {label}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: any) {
  return (
    <div className="glass-panel p-6">
      <h3 className="text-textMuted text-sm mb-2">{title}</h3>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
    </div>
  );
}
