import { useState } from 'react';
import { Play, Pause, Square, Activity, Info, Check, Image as ImageIcon, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { api } from '../../api';

export default function DashboardView({ project, stats, onStatsUpdate }: { project: any, stats: any, onStatsUpdate: () => void }) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(() => localStorage.getItem("selectedModel") || "nvidia/segformer-b3-finetuned-ade-512-512");
  if (!project) return <div className="p-8">No project selected</div>;
  if (!stats) return <div className="p-8 text-textMuted flex items-center gap-3"><Activity className="animate-spin text-primary" /> Loading stats from database...</div>;

  const progress = stats.total_images > 0 
    ? Math.round((stats.processed_images / stats.total_images) * 100) 
    : 0;

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setSelectedModel(val);
    localStorage.setItem("selectedModel", val);
  };

  const handleAction = async (action: 'auto-label' | 'pause' | 'resume' | 'stop') => {
    try {
      if (action === 'auto-label') {
        setFeedback("Processing Started");
        await api.labeling.autoLabelAll(project.id, selectedModel);
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
    <div className="flex-1 p-8 overflow-y-auto bg-background">
      <div className="flex flex-col xl:flex-row gap-6 mb-8">
        
        {/* Controls Panel */}
        <div className="glass-panel p-6 flex-1 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <h3 className="text-xl font-bold mb-6 flex items-center gap-3 relative z-10 text-textMain">
            <div className={`p-2 rounded-xl ${isRunning ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.4)]' : isPaused ? 'bg-amber-500/20 text-amber-400' : 'bg-white/5 text-textMuted'}`}>
              <Activity size={22} className={isRunning ? 'animate-pulse' : ''} />
            </div>
            Processing Controls
          </h3>
          
          <div className="flex flex-col gap-4 mb-4 relative z-10">
            <div className="flex items-center gap-4 bg-white/5 p-3 rounded-xl border border-white/5">
              <label className="text-sm font-semibold tracking-wider uppercase text-textMuted w-20">Model:</label>
              <select 
                className="bg-black/30 border border-white/10 text-textMain text-sm rounded-lg px-3 py-2.5 outline-none focus:border-primary transition-colors flex-1"
                value={selectedModel}
                onChange={handleModelChange}
                disabled={!isStopped}
              >
                <option value="nvidia/segformer-b3-finetuned-ade-512-512">SegFormer-b3 (Dense Segmentation Pipeline)</option>
                <option value="nvidia/LocateAnything-3B">LocateAnything-3B (VLM Object Grounding)</option>
              </select>
            </div>
            
            <div className="flex flex-wrap gap-4">
            <button 
              onClick={() => handleAction('auto-label')} 
              disabled={!isStopped} 
              title="Start Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-emerald-500/20 to-emerald-600/20 text-emerald-400 hover:from-emerald-500/30 hover:to-emerald-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-emerald-500/30 hover:border-emerald-400/50 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]"
            >
              <Play size={20} /> Start
            </button>
            <button 
              onClick={() => handleAction('pause')} 
              disabled={!isRunning} 
              title="Pause Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-amber-500/20 to-amber-600/20 text-amber-400 hover:from-amber-500/30 hover:to-amber-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-amber-500/30 hover:border-amber-400/50 hover:shadow-[0_0_20px_rgba(245,158,11,0.3)]"
            >
              <Pause size={20} /> Pause
            </button>
            <button 
              onClick={() => handleAction('resume')} 
              disabled={!isPaused} 
              title="Resume Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-primary/20 to-primary/30 text-primary hover:from-primary/30 hover:to-primary/40 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-primary/30 hover:border-primary/50 hover:shadow-[0_0_20px_rgba(99,102,241,0.3)]"
            >
              <Play size={20} /> Resume
            </button>
            <button 
              onClick={() => handleAction('stop')} 
              disabled={isStopped} 
              title="Stop Processing"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-red-500/20 to-red-600/20 text-red-400 hover:from-red-500/30 hover:to-red-600/30 rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all border border-red-500/30 hover:border-red-400/50 hover:shadow-[0_0_20px_rgba(239,68,68,0.3)]"
            >
              <Square size={20} /> Stop
            </button>
            </div>
          </div>

          {feedback && (
            <div className="absolute bottom-4 right-6 text-emerald-400 font-medium text-sm flex items-center gap-2 animate-in slide-in-from-bottom-2 fade-in">
              <Info size={16} /> {feedback}
            </div>
          )}
        </div>

        {/* Processing Information Panel */}
        <div className="glass-panel p-6 flex-1 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-bl from-accent/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <h3 className="text-xl font-bold mb-6 text-textMain relative z-10 flex items-center gap-3">
            <Clock size={22} className="text-accent" />
            Processing Stats
          </h3>
          <div className="grid grid-cols-2 gap-y-6 gap-x-8 text-sm relative z-10">
            <div className="flex flex-col bg-white/5 p-4 rounded-xl border border-white/5">
              <span className="text-textMuted mb-2 text-xs uppercase tracking-wider font-semibold">Engine Status</span>
              <span className={`text-lg font-bold flex items-center gap-2 ${isRunning ? 'text-emerald-400' : isPaused ? 'text-amber-400' : 'text-textMuted'}`}>
                {isRunning && <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_10px_rgba(52,211,153,0.8)]"></span>}
                {state === 'RUNNING' ? 'Running' : state === 'PAUSED' ? 'Paused' : 'Stopped'}
              </span>
            </div>
            <div className="flex flex-col bg-white/5 p-4 rounded-xl border border-white/5">
              <span className="text-textMuted mb-2 text-xs uppercase tracking-wider font-semibold">Queue Size</span>
              <span className="text-lg font-bold text-textMain">{stats.queue_size} <span className="text-xs text-textMuted font-normal">items</span></span>
            </div>
            <div className="flex flex-col bg-white/5 p-4 rounded-xl border border-white/5">
              <span className="text-textMuted mb-2 text-xs uppercase tracking-wider font-semibold">Processed</span>
              <div className="flex items-end gap-2">
                <span className="text-lg font-bold text-primary">{stats.processed_images}</span>
                <span className="text-sm text-textMuted mb-0.5">/ {stats.total_images}</span>
              </div>
            </div>
            <div className="flex flex-col bg-white/5 p-4 rounded-xl border border-white/5">
              <span className="text-textMuted mb-2 text-xs uppercase tracking-wider font-semibold">Est. Time Left</span>
              <span className="text-lg font-bold text-textMain">{etaMinutes} <span className="text-xs text-textMuted font-normal">minutes</span></span>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-8 glass-panel p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-accent/5 to-transparent"></div>
        <div className="relative z-10">
          <div className="flex justify-between mb-3">
            <span className="text-textMuted font-medium tracking-wide">Overall Pipeline Progress</span>
            <span className="font-bold text-xl text-primary">{progress}%</span>
          </div>
          <div className="w-full bg-black/40 rounded-full h-3 overflow-hidden border border-white/10 shadow-inner">
            <div 
              className="h-3 transition-all duration-700 ease-in-out relative rounded-full bg-gradient-to-r from-primary to-accent" 
              style={{ width: `${progress}%` }}
            >
              <div className="absolute inset-0 bg-white/20 animate-[pulse_2s_ease-in-out_infinite]"></div>
            </div>
          </div>
          <div className="flex justify-between mt-3 text-sm text-textMuted font-medium">
            <span className="flex items-center gap-1.5"><CheckCircle size={14} className="text-emerald-400"/> {stats.processed_images} processed</span>
            <span className="flex items-center gap-1.5"><Clock size={14} className="text-amber-400"/> {stats.remaining_images} remaining</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="Total Images" value={stats.total_images} color="text-textMain" icon={<ImageIcon size={20} />} />
        <StatCard title="Review Tasks Sent" value={stats.review_tasks_sent || 0} color="text-secondary" icon={<Info size={20} />} />
        <StatCard title="Human Reviewed" value={stats.review_tasks_reviewed || 0} color="text-emerald-400" icon={<CheckCircle size={20} />} />
        <StatCard title="Human Corrected" value={stats.review_tasks_corrected || 0} color="text-amber-400" icon={<AlertCircle size={20} />} />
        
        <StatCard title="Review Pending" value={stats.review_tasks_pending || 0} color="text-orange-400" icon={<Clock size={20} />} />
        <StatCard title="Images Processed" value={stats.processed_images} color="text-primary" icon={<Activity size={20} />} />
        <StatCard title="Images Remaining" value={stats.remaining_images} color="text-accent" icon={<ImageIcon size={20} />} />
        <StatCard title="Avg Confidence" value={`${(stats.avg_confidence * 100).toFixed(1)}%`} color="text-emerald-300" icon={<Check size={20} />} />
      </div>

      <div className="glass-panel p-6 mb-8 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-64 h-64 bg-accent/5 rounded-full blur-3xl group-hover:bg-accent/10 transition-colors duration-700 pointer-events-none"></div>
        <h3 className="text-xl font-bold mb-6 text-textMain flex items-center gap-3 relative z-10">
          <Activity size={22} className="text-accent" /> Class Distribution
        </h3>
        {Object.keys(stats.class_distribution || {}).length === 0 ? (
          <p className="text-textMuted text-sm relative z-10">No annotations yet</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 relative z-10">
            {Object.entries(stats.class_distribution).map(([cls, count]: [string, any]) => {
              const maxCount = Math.max(...Object.values(stats.class_distribution as Record<string, number>));
              const percentage = (count / maxCount) * 100;
              return (
                <div key={cls} className="bg-white/5 rounded-xl p-4 border border-white/5 hover:border-white/20 hover:bg-white/10 transition-all duration-300 cursor-default group/card">
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-sm font-semibold text-textMain truncate pr-2 group-hover/card:text-white transition-colors">{cls}</span>
                    <span className="text-xs font-mono text-textMuted bg-black/40 px-2 py-0.5 rounded shadow-inner">{count}</span>
                  </div>
                  <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden shadow-inner">
                    <div className="h-full bg-gradient-to-r from-primary to-accent rounded-full transition-all duration-1000" style={{ width: `${percentage}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Hardware Telemetry Panel */}
      {stats.hardware && (
        <div className="mb-8 glass-panel p-6 border border-primary/20 bg-primary/5 relative overflow-hidden">
          <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10 mix-blend-overlay"></div>
          <div className="flex items-center justify-between mb-6 relative z-10">
            <h3 className="text-lg font-bold text-primary flex items-center gap-2">
              <Activity size={20} /> Runtime Verification
            </h3>
            <div className={`px-4 py-1.5 rounded-full text-xs font-bold shadow-lg ${stats.hardware.device_type === 'cuda' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
              {stats.hardware.device_type === 'cuda' ? 'CUDA Active' : 'CPU Fallback'}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6 relative z-10">
            <TelemetryMetric label="Compute Device" value={stats.hardware.device_name} />
            <TelemetryMetric label="GPU Utilization" value={`${stats.hardware.gpu_utilization_pct}%`} />
            <TelemetryMetric label="VRAM Usage" value={`${stats.hardware.vram_used_gb} / ${stats.hardware.vram_total_gb} GB`} />
            <TelemetryMetric label="Images / Min" value={`${stats.hardware.images_per_minute} IPM`} />
            <TelemetryMetric label="Avg Inference" value={`${stats.hardware.avg_inference_ms} ms`} />
          </div>
        </div>
      )}

      {/* Bulk Cleanup Tools */}
      <BulkCleanupTools project={project} onStatsUpdate={onStatsUpdate} />
    </div>
  );
}

function TelemetryMetric({ label, value }: { label: string, value: string | number }) {
  return (
    <div className="bg-black/20 p-4 rounded-xl border border-white/5 backdrop-blur-sm">
      <div className="text-[10px] text-textMuted uppercase tracking-wider font-semibold mb-1">{label}</div>
      <div className="font-bold text-textMain text-sm truncate">{value}</div>
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
    processed: "Reset All Processed Images",
    reviewed: "Reset All Reviewed Images",
    accepted: "Reset All Accepted Images",
    rejected: "Reset All Rejected Images",
    completed_queue: "Clear Completed Queue",
    all: "Delete Entire Project"
  };

  return (
    <div className="glass-panel p-6 border border-red-500/20 bg-red-500/5 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-500/0 via-red-500/50 to-red-500/0"></div>
      <h3 className="text-lg font-bold text-red-400 mb-6 flex items-center gap-2">
        <AlertCircle size={20} /> Danger Zone: Bulk Cleanup Tools
      </h3>
      
      <div className="mb-6 bg-black/20 p-4 rounded-xl border border-red-500/10">
        <label className="flex items-center gap-3 cursor-pointer group w-max">
          <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${deleteSourceFiles ? 'bg-red-500 border-red-500' : 'border-white/20 group-hover:border-white/40'}`}>
            {deleteSourceFiles && <Check size={14} className="text-white" />}
          </div>
          <input type="checkbox" className="hidden" checked={deleteSourceFiles} onChange={e => setDeleteSourceFiles(e.target.checked)} />
          <span className="text-sm font-medium text-textMuted group-hover:text-textMain transition-colors">Also Delete Source Files (.jpg, .png) from Disk</span>
        </label>
        {deleteSourceFiles && <p className="text-xs text-red-400 mt-2 ml-8 font-medium">Warning: This cannot be undone. DB records and source files will be permanently deleted.</p>}
        {!deleteSourceFiles && <p className="text-xs text-secondary mt-2 ml-8">Info: Images will simply be reset to 'pending' state and remain in the project.</p>}
      </div>

      <div className="flex flex-wrap gap-4">
        {Object.entries(actionLabels).map(([key, label]) => (
          <div key={key}>
            {confirmAction === key ? (
              <div className="flex items-center gap-2 animate-in fade-in zoom-in duration-200 bg-red-500/10 p-1.5 rounded-lg border border-red-500/20">
                <span className="text-sm font-bold text-red-400 mx-2">Confirm?</span>
                <button disabled={isDeleting} onClick={() => handleCleanup(key)} className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-semibold transition-colors disabled:opacity-50 shadow-lg shadow-red-900/50">
                  {isDeleting ? 'Processing...' : (deleteSourceFiles || key === 'all' || key === 'completed_queue' ? 'Yes, Delete' : 'Yes, Reset')}
                </button>
                <button disabled={isDeleting} onClick={() => setConfirmAction(null)} className="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-textMain rounded text-sm font-semibold transition-colors disabled:opacity-50">
                  Cancel
                </button>
              </div>
            ) : (
              <button 
                onClick={() => setConfirmAction(key)}
                className="px-4 py-2.5 bg-red-500/5 hover:bg-red-500/15 text-red-400 border border-red-500/20 rounded-xl text-sm font-semibold transition-all hover:border-red-500/40"
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

function StatCard({ title, value, color, icon }: any) {
  return (
    <div className="glass-panel p-6 relative overflow-hidden group">
      <div className="absolute -right-6 -top-6 w-24 h-24 bg-white/5 rounded-full blur-2xl group-hover:bg-white/10 transition-all duration-500 pointer-events-none"></div>
      <div className="flex justify-between items-start mb-4 relative z-10">
        <h3 className="text-textMuted text-sm font-medium">{title}</h3>
        {icon && <div className={`p-2 rounded-lg bg-white/5 ${color} shadow-inner`}>{icon}</div>}
      </div>
      <p className={`text-3xl font-bold tracking-tight ${color} relative z-10`}>{value}</p>
    </div>
  );
}
