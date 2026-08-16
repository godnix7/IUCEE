import React, { useEffect, useState } from 'react';
import { Building, ShieldCheck } from 'lucide-react';
import { api } from '../../api';

export const BenchmarkView: React.FC = () => {
  const [benchmark, setBenchmark] = useState<any>(null);

  useEffect(() => {
    api.analytics.getDashboardStats().then(data => {
      if (data.recent_analyses.length > 0) {
        api.analytics.getBenchmark(data.recent_analyses[0].id).then(setBenchmark);
      }
    });
  }, []);

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-5xl mx-auto space-y-6">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Building className="text-blue-400" size={24} /> Urban Infrastructure Benchmarks
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Comparative analysis against international urban planning infrastructure standards per 1,000 citizens
        </p>
      </div>

      {benchmark ? (
        <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400">Composite Score Index</span>
              <h2 className="text-3xl font-bold text-emerald-400">{benchmark.infrastructure_score}/100</h2>
            </div>

            <div className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium rounded-lg flex items-center gap-2">
              <ShieldCheck size={16} /> Verified Benchmark
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                <tr>
                  <th className="p-3">Urban Indicator</th>
                  <th className="p-3">Computed Value</th>
                  <th className="p-3">Standard Target</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-200">
                {Object.entries(benchmark.metrics || {}).map(([key, item]: [string, any]) => (
                  <tr key={key}>
                    <td className="p-3 font-medium capitalize">{key.replace(/_/g, ' ')}</td>
                    <td className="p-3 font-bold text-white">{item.computed} {item.unit}</td>
                    <td className="p-3 text-slate-400">{item.benchmark_target} {item.unit}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                        item.status === 'Sufficient' || item.status === 'Optimal' || item.status === 'Balanced' || item.status === 'Adequate'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                      }`}>
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-slate-500 bg-[#111827] border border-slate-800 rounded-2xl">
          Run an AI imagery analysis to view urban benchmarks.
        </div>
      )}
    </div>
  );
};
