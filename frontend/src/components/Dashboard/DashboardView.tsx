import React, { useEffect, useState } from 'react';
import {
  Layers,
  Sparkles,
  TrendingUp,
  MapPin,
  Users
} from 'lucide-react';
import { api } from '../../api';
import { useToast } from '../../context/ToastContext';
import type { DashboardStats, AnalyticsResponse } from '../../types';

export const DashboardView: React.FC<{ onNavigateMap: () => void; onNavigateAnalysis: () => void }> = ({
  onNavigateAnalysis
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    fetchStats();
    // No more 5s polling for the entire dashboard to prevent jarring UX, just load once or on refresh
  }, []);

  const fetchStats = async () => {
    try {
      const data = await api.analytics.getDashboardStats();
      setStats(data);
      if (data.recent_analyses.length > 0 && !selectedAnalysisId) {
        // Default to most recent completed
        const completed = data.recent_analyses.find(a => a.status === 'completed');
        if (completed) {
          handleSelectAnalysis(completed.id);
        } else {
          handleSelectAnalysis(data.recent_analyses[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch dashboard stats', err);
      addToast('Failed to load dashboard statistics.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAnalysis = async (id: number) => {
    setSelectedAnalysisId(id);
    setLoadingAnalytics(true);
    setAnalytics(null);
    try {
      const data = await api.analytics.getAnalysisAnalytics(id);
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to fetch analytics', err);
      addToast('Failed to fetch analysis analytics.', 'error');
    } finally {
      setLoadingAnalytics(false);
    }
  };

  if (loading || !stats) {
    return (
      <div className="flex-1 bg-[#0b0f19] text-white flex items-center justify-center">
        <div className="flex items-center gap-3 text-blue-400">
          <Sparkles className="animate-spin" size={24} />
          <span>Loading Infrastructure Intelligence Dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-[#0b0f19] text-slate-100 p-6 overflow-y-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Urban Infrastructure Intelligence
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time geospatial analytics & AI aerial segmentation metrics
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select 
            className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
            value={selectedAnalysisId || ''}
            onChange={(e) => handleSelectAnalysis(Number(e.target.value))}
          >
            <option value="" disabled>Select an analysis</option>
            {stats.recent_analyses.map(a => (
              <option key={a.id} value={a.id}>
                Analysis #{a.id} - {a.filename} ({a.status})
              </option>
            ))}
          </select>

          <button
            onClick={onNavigateAnalysis}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 shadow-lg shadow-blue-600/20"
          >
            <Sparkles size={14} /> New AI Analysis
          </button>
        </div>
      </div>

      {!selectedAnalysisId ? (
        <div className="p-12 text-center text-slate-500 bg-[#111827] border border-slate-800 rounded-2xl">
          Select an analysis from the dropdown above.
        </div>
      ) : loadingAnalytics ? (
        <div className="p-12 text-center text-slate-500 flex items-center justify-center gap-3 bg-[#111827] border border-slate-800 rounded-2xl">
          <Sparkles className="animate-spin text-blue-400" size={20} />
          <span>Analytics are being calculated...</span>
        </div>
      ) : analytics?.status && analytics.status !== 'completed' ? (
        <div className="p-12 text-center text-slate-500 bg-[#111827] border border-slate-800 rounded-2xl">
          Analytics are not yet available. Current status: {analytics.status}
        </div>
      ) : analytics && !analytics.status ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              title="Infrastructure Score"
              value={analytics.score !== null ? `${analytics.score}/100` : 'Unavailable'}
              subtitle={analytics.score !== null ? `Formula v${analytics.formula_version || '1.0'}` : 'Missing benchmarks or population'}
              icon={<TrendingUp className="text-emerald-400" size={20} />}
            />
            <KpiCard
              title="Analysis Area"
              value={analytics.area_sq_km !== null ? `${analytics.area_sq_km} km²` : 'Unavailable'}
              subtitle="PostGIS Footprint"
              icon={<MapPin className="text-blue-400" size={20} />}
            />
            <KpiCard
              title="Population"
              value={analytics.population.count !== null ? analytics.population.count.toLocaleString() : 'Unavailable'}
              subtitle={analytics.population.source ? `Source: ${analytics.population.source}` : 'Population not configured'}
              icon={<Users className="text-amber-400" size={20} />}
            />
            <KpiCard
              title="Road Coverage"
              value={analytics.infrastructure.road_coverage_pct !== null ? `${analytics.infrastructure.road_coverage_pct}%` : 'Unavailable'}
              subtitle="AI Segmented Area"
              icon={<Layers className="text-cyan-400" size={20} />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-xl">
              <h3 className="text-sm font-semibold text-white mb-4">Infrastructure Composition</h3>
              <div className="space-y-4">
                <CompositionBar label="Building Coverage" pct={analytics.infrastructure.building_coverage_pct} color="bg-red-500" />
                <CompositionBar label="Tree Canopy" pct={analytics.infrastructure.tree_cover_pct} color="bg-green-500" />
                <CompositionBar label="Water Bodies" pct={analytics.infrastructure.water_cover_pct} color="bg-cyan-500" />
                <CompositionBar label="Barren Land" pct={analytics.infrastructure.barren_cover_pct} color="bg-amber-700" />
                <CompositionBar label="Agriculture" pct={analytics.infrastructure.agriculture_cover_pct} color="bg-lime-500" />
              </div>
            </div>

            <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-xl">
              <h3 className="text-sm font-semibold text-white mb-4">Community Facilities (OSM)</h3>
              <div className="grid grid-cols-2 gap-4">
                <FacilityCard label="Hospitals" count={analytics.facilities.hospitals} per1000={analytics.normalized.hospitals_per_1000} />
                <FacilityCard label="Schools" count={analytics.facilities.schools} per1000={analytics.normalized.schools_per_1000} />
                <FacilityCard label="Police Stations" count={analytics.facilities.police} per1000={null} />
                <FacilityCard label="Fire Stations" count={analytics.facilities.fire_stations} per1000={null} />
              </div>
              {analytics.facilities.hospitals === null && (
                <p className="text-xs text-amber-500/80 mt-4 text-center">
                  Facility metrics unavailable because OSM enrichment failed or is pending.
                </p>
              )}
            </div>
          </div>

          <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-xl">
             <h3 className="text-sm font-semibold text-white mb-4">Infrastructure Score Breakdown</h3>
             {analytics.score === null ? (
               <div className="text-sm text-slate-400 text-center py-4">
                  Score is unavailable. Ensure population is provided and benchmark definitions exist.
               </div>
             ) : (
               <div className="overflow-x-auto">
                 <table className="w-full text-left text-xs">
                   <thead className="bg-slate-900/60 text-slate-400 uppercase text-[10px]">
                     <tr>
                       <th className="p-2.5">Component</th>
                       <th className="p-2.5">Actual Value</th>
                       <th className="p-2.5">Benchmark Target</th>
                       <th className="p-2.5">Points</th>
                     </tr>
                   </thead>
                   <tbody className="divide-y divide-slate-800 text-slate-300">
                     {Object.entries(analytics.component_scores || {}).map(([key, data]: [string, any]) => (
                       <tr key={key} className="hover:bg-slate-800/40">
                         <td className="p-2.5 font-medium capitalize text-white">{key.replace(/_/g, ' ')}</td>
                         <td className="p-2.5">{data.value}</td>
                         <td className="p-2.5 text-slate-400">{data.target}</td>
                         <td className="p-2.5 text-emerald-400 font-bold">{data.score} / {data.max}</td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               </div>
             )}
          </div>
        </>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-4 border-t border-slate-800/50">
        <div className="lg:col-span-2 bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Global Platform Status</h3>
            <span className="text-xs text-slate-400">{stats.total_analyses} Total Analyses Processed</span>
          </div>
          <div className="flex items-center gap-6">
             <div className="text-center p-4 bg-slate-900/50 rounded-lg flex-1 border border-slate-800/50">
                <div className="text-2xl font-bold text-blue-400">{stats.active_users_count}</div>
                <div className="text-[10px] text-slate-500 uppercase mt-1">Active Planners</div>
             </div>
             <div className="text-center p-4 bg-slate-900/50 rounded-lg flex-1 border border-slate-800/50">
                <div className="text-2xl font-bold text-amber-400">{stats.processing_queue_count}</div>
                <div className="text-[10px] text-slate-500 uppercase mt-1">Jobs Queued</div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const KpiCard: React.FC<{ title: string; value: string; subtitle?: string; icon: React.ReactNode }> = ({
  title, value, subtitle, icon
}) => (
  <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 shadow-xl flex items-start justify-between">
    <div>
      <p className="text-xs text-slate-400 mb-1">{title}</p>
      <h2 className="text-2xl font-bold text-white tracking-tight">{value}</h2>
      {subtitle && <p className="text-[11px] text-slate-500 mt-1">{subtitle}</p>}
    </div>
    <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800">{icon}</div>
  </div>
);

const CompositionBar: React.FC<{ label: string; pct: number | null; color: string }> = ({ label, pct, color }) => (
  <div className="flex items-center gap-3">
    <div className="w-24 text-xs text-slate-400 truncate">{label}</div>
    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden flex">
      {pct !== null && <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />}
    </div>
    <div className="w-12 text-right text-xs font-medium text-white">{pct !== null ? `${pct}%` : 'N/A'}</div>
  </div>
);

const FacilityCard: React.FC<{ label: string; count: number | null; per1000: number | null }> = ({ label, count, per1000 }) => (
  <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
    <div className="text-[11px] text-slate-400 mb-1">{label}</div>
    <div className="text-xl font-bold text-white">{count !== null ? count : '-'}</div>
    {per1000 !== null && (
      <div className="text-[10px] text-emerald-400 mt-1">{per1000} per 1k pop</div>
    )}
  </div>
);
