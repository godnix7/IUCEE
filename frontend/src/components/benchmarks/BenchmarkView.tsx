import React, { useEffect, useState } from 'react';
import { Building, ShieldCheck, Sparkles, Plus, Edit2, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { DashboardStats, AnalyticsResponse } from '../../types';

export const BenchmarkView: React.FC = () => {
  const { isAdmin } = useAuth();
  const { addToast } = useToast();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Benchmark Admin State
  const [benchmarks, setBenchmarks] = useState<any[]>([]);
  const [showAdmin, setShowAdmin] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [formData, setFormData] = useState({ indicator: '', unit: '', target_value: 0, source: '', reference_name: '', notes: '' });

  const fetchBenchmarks = async () => {
    try {
      const data = await api.benchmarks.list();
      setBenchmarks(data);
    } catch (e) {
      console.error(e);
      addToast('Failed to load benchmarks.', 'error');
    }
  };

  useEffect(() => {
    fetchBenchmarks();
    api.analytics.getDashboardStats().then(data => {
      setStats(data);
      if (data.recent_analyses.length > 0) {
        const completed = data.recent_analyses.find(a => a.status === 'completed');
        if (completed) {
          handleSelectAnalysis(completed.id);
        } else {
          handleSelectAnalysis(data.recent_analyses[0].id);
        }
      }
    }).finally(() => setLoading(false));
  }, []);

  const handleSelectAnalysis = async (id: number) => {
    setSelectedAnalysisId(id);
    setAnalytics(null);
    try {
      const data = await api.analytics.getAnalysisAnalytics(id);
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to fetch analytics', err);
      addToast('Failed to fetch analysis analytics.', 'error');
    }
  };

  const handleSaveBenchmark = async () => {
    try {
      if (editingId) {
        await api.benchmarks.update(editingId, formData);
      } else {
        await api.benchmarks.create(formData);
      }
      setEditingId(null);
      setFormData({ indicator: '', unit: '', target_value: 0, source: '', reference_name: '', notes: '' });
      fetchBenchmarks();
      addToast('Benchmark saved successfully.', 'success');
    } catch (e) {
      console.error(e);
      addToast('Failed to save benchmark.', 'error');
    }
  };

  const confirmDeleteBenchmark = async () => {
    if (!deletingId) return;
    try {
      await api.benchmarks.delete(deletingId);
      setDeletingId(null);
      fetchBenchmarks();
      addToast('Benchmark deleted.', 'success');
    } catch (e) {
      console.error(e);
      addToast('Failed to delete benchmark.', 'error');
    }
  };

  const handleDeleteBenchmark = (id: number) => {
    setDeletingId(id);
  };

  if (loading || !stats) {
    return (
      <div className="flex-1 bg-[#0b0f19] text-white flex items-center justify-center">
        <div className="flex items-center gap-3 text-blue-400">
          <Sparkles className="animate-spin" size={24} />
          <span>Loading Benchmarks...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-5xl mx-auto space-y-6">
      <div className="border-b border-slate-800 pb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building className="text-blue-400" size={24} /> Urban Infrastructure Benchmarks
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Comparative analysis against configured urban planning infrastructure standards
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          {isAdmin && (
            <button
              onClick={() => setShowAdmin(!showAdmin)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700"
            >
              {showAdmin ? 'View Analytics' : 'Manage Benchmarks (Admin)'}
            </button>
          )}
          
          {!showAdmin && (
            <select 
              className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
              value={selectedAnalysisId || ''}
              onChange={(e) => handleSelectAnalysis(Number(e.target.value))}
            >
              <option value="" disabled>Select an analysis</option>
              {stats.recent_analyses.map(a => (
                <option key={a.id} value={a.id}>
                  Analysis #{a.id} - {a.filename}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {showAdmin && isAdmin ? (
        <div className="space-y-6">
          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-semibold text-white">Configured Benchmarks</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Indicator</th>
                    <th className="p-3">Target</th>
                    <th className="p-3">Source</th>
                    <th className="p-3">Reference</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-200">
                  {benchmarks.map(b => (
                    <tr key={b.id}>
                      <td className="p-3 font-medium capitalize text-blue-400">{b.indicator}</td>
                      <td className="p-3 font-bold text-white">{b.target_value} {b.unit}</td>
                      <td className="p-3 text-slate-400">{b.source}</td>
                      <td className="p-3 text-slate-400">{b.reference_name}</td>
                      <td className="p-3 text-right space-x-2">
                        <button
                          onClick={() => { setEditingId(b.id); setFormData(b); }}
                          className="p-1.5 text-blue-400 hover:bg-blue-500/10 rounded"
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          onClick={() => handleDeleteBenchmark(b.id)}
                          className="p-1.5 text-red-400 hover:bg-red-500/10 rounded"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {benchmarks.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-slate-500">
                        No benchmarks configured.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Plus size={18} className="text-blue-400"/> {editingId ? 'Edit Benchmark' : 'Add New Benchmark'}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Indicator (e.g. tree_cover_pct, hospitals_per_1000)</label>
                <input type="text" value={formData.indicator} onChange={e => setFormData({...formData, indicator: e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Unit (e.g. %, per 1,000)</label>
                <input type="text" value={formData.unit} onChange={e => setFormData({...formData, unit: e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Target Value</label>
                <input type="number" step="0.1" value={formData.target_value} onChange={e => setFormData({...formData, target_value: parseFloat(e.target.value)})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Source (e.g. UrbanSense Default, WHO)</label>
                <input type="text" value={formData.source} onChange={e => setFormData({...formData, source: e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Reference Name (e.g. 2026 Target)</label>
                <input type="text" value={formData.reference_name} onChange={e => setFormData({...formData, reference_name: e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Notes (Optional)</label>
                <input type="text" value={formData.notes} onChange={e => setFormData({...formData, notes: e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-white" />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              {editingId && (
                <button
                  onClick={() => { setEditingId(null); setFormData({ indicator: '', unit: '', target_value: 0, source: '', reference_name: '', notes: '' }); }}
                  className="px-4 py-2 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
              )}
              <button
                onClick={handleSaveBenchmark}
                className="px-4 py-2 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg"
              >
                Save Benchmark
              </button>
            </div>
          </div>
        </div>
      ) : !selectedAnalysisId ? (
        <div className="p-8 text-center text-slate-500 bg-[#111827] border border-slate-800 rounded-2xl">
          Select an analysis.
        </div>
      ) : analytics && !analytics.status ? (
        <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400">Composite Score Index</span>
              <h2 className="text-3xl font-bold text-emerald-400">
                {analytics.score !== null ? `${analytics.score}/100` : 'Unavailable'}
              </h2>
            </div>

            <div className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium rounded-lg flex items-center gap-2">
              <ShieldCheck size={16} /> Verified Benchmark
            </div>
          </div>

          {analytics.score === null ? (
            <div className="text-sm text-slate-400 text-center py-4 bg-slate-900/50 rounded-lg border border-slate-800">
               No reference benchmark configured, or Population not configured.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Indicator</th>
                    <th className="p-3">Actual</th>
                    <th className="p-3">Target</th>
                    <th className="p-3">Gap</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-200">
                  {Object.entries(analytics.component_scores || {}).map(([key, item]: [string, any]) => {
                    const diff = item.value - item.target;
                    const isPct = key.includes('cover');
                    const gapLabel = diff > 0 ? `+${diff.toFixed(2)}` : diff.toFixed(2);
                    
                    let statusLabel = 'Balanced';
                    let statusColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
                    
                    if (diff < 0) {
                      statusLabel = 'Below Reference';
                      statusColor = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
                    } else if (diff > 0) {
                      statusLabel = 'Above Reference';
                    }

                    return (
                      <tr key={key}>
                        <td className="p-3 font-medium capitalize">{key.replace(/_/g, ' ')}</td>
                        <td className="p-3 font-bold text-white">{item.value.toFixed(2)}{isPct ? '%' : ''}</td>
                        <td className="p-3 text-slate-400">{item.target.toFixed(2)}{isPct ? '%' : ''}</td>
                        <td className="p-3 text-slate-400">{gapLabel} {isPct ? 'pp' : ''}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${statusColor}`}>
                            {statusLabel}
                          </span>
                        </td>
                        <td className="p-3 text-slate-500">{item.source || 'Configured Reference'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="p-8 text-center text-slate-500 bg-[#111827] border border-slate-800 rounded-2xl">
          Analytics are being calculated.
        </div>
      )}
      
      {/* Custom Delete Confirmation Modal */}
      {deletingId && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-2xl max-w-sm w-full space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-white">Delete Benchmark?</h3>
            <p className="text-sm text-slate-400">
              Are you sure you want to delete this benchmark definition? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setDeletingId(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteBenchmark}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-red-600/20"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
