import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ListChecks, RefreshCw, XCircle, RotateCcw, ScanEye, Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

interface Job {
  id: number;
  analysis_id: number;
  status: string;
  progress: number;
  current_stage?: string | null;
  message?: string | null;
  attempt: number;
  max_attempts: number;
  created_at: string;
  updated_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  running: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  queued: 'bg-slate-600/20 text-slate-300 border-slate-600/40',
  retrying: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  failed: 'bg-red-500/10 text-red-400 border-red-500/30',
  cancelled: 'bg-slate-700/30 text-slate-400 border-slate-600/40',
};

const FILTERS = ['all', 'queued', 'running', 'completed', 'failed', 'cancelled'];

export const JobsView: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const canManage = user?.role === 'admin' || user?.role === 'planner';

  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [acting, setActing] = useState<number | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.jobs.list(filter === 'all' ? {} : { status: filter });
      setJobs(data.items || []);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load jobs');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  // Poll while any job is active
  useEffect(() => {
    const hasActive = jobs.some((j) => ['queued', 'running', 'retrying'].includes(j.status));
    if (!hasActive) return;
    const t = setInterval(() => load(true), 3000);
    return () => clearInterval(t);
  }, [jobs, load]);

  const act = async (id: number, action: 'cancel' | 'retry') => {
    setActing(id);
    try {
      await api.jobs[action](id);
      addToast(action === 'cancel' ? 'Job cancellation requested' : 'Job retry initiated', 'success');
      await load(true);
    } catch (e: any) {
      addToast(e.message || `Failed to ${action} job`, 'error');
    } finally {
      setActing(null);
    }
  };

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ListChecks className="text-blue-400" size={24} /> Processing Jobs
            </h1>
            <p className="text-xs text-slate-400 mt-1">Live status of imagery analysis jobs across your projects.</p>
          </div>
          <button onClick={() => load()} className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300" title="Refresh">
            <RefreshCw size={16} />
          </button>
        </div>

        <div className="flex gap-1.5 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs capitalize border ${
                filter === f ? 'bg-blue-600 text-white border-blue-500' : 'bg-slate-900 text-slate-400 border-slate-700 hover:border-slate-600'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} /> Loading jobs…
          </div>
        ) : error ? (
          <div className="p-6 text-center">
            <div className="text-red-400 text-sm mb-3">{error}</div>
            <button onClick={() => load()} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs">Retry</button>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-12 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl">
            No processing jobs {filter !== 'all' ? `with status "${filter}"` : 'yet'}.
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.map((j) => {
              const active = ['queued', 'running', 'retrying'].includes(j.status);
              return (
                <div key={j.id} className="bg-[#111827] border border-slate-800 rounded-xl p-4">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-500">Job #{j.id}</span>
                      <span className="text-sm font-medium">Analysis #{j.analysis_id}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[11px] border capitalize ${STATUS_STYLES[j.status] || STATUS_STYLES.queued}`}>
                        {j.status}
                      </span>
                      {j.current_stage && <span className="text-[11px] text-slate-400">{j.current_stage}</span>}
                    </div>
                    <div className="flex items-center gap-1.5">
                      {j.status === 'completed' && (
                        <button onClick={() => navigate(`/analyses/${j.analysis_id}/review`)} className="px-2.5 py-1 rounded-lg text-[11px] bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-1">
                          <ScanEye size={12} /> Review
                        </button>
                      )}
                      {canManage && active && (
                        <button onClick={() => act(j.id, 'cancel')} disabled={acting === j.id} className="px-2.5 py-1 rounded-lg text-[11px] bg-slate-700 hover:bg-red-600/80 text-white flex items-center gap-1 disabled:opacity-40">
                          <XCircle size={12} /> Cancel
                        </button>
                      )}
                      {canManage && ['failed', 'cancelled'].includes(j.status) && (
                        <button onClick={() => act(j.id, 'retry')} disabled={acting === j.id} className="px-2.5 py-1 rounded-lg text-[11px] bg-amber-600 hover:bg-amber-500 text-white flex items-center gap-1 disabled:opacity-40">
                          <RotateCcw size={12} /> Retry
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all ${j.status === 'failed' ? 'bg-red-500' : j.status === 'completed' ? 'bg-emerald-500' : 'bg-blue-500'}`}
                        style={{ width: `${Math.max(0, Math.min(100, j.progress))}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-slate-400 tabular-nums w-10 text-right">{j.progress}%</span>
                  </div>

                  {j.message && <div className="mt-1.5 text-[11px] text-slate-500 truncate">{j.message}</div>}
                  {j.attempt > 1 && <div className="mt-0.5 text-[10px] text-slate-600">Attempt {j.attempt}/{j.max_attempts}</div>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
