import React, { useEffect, useState } from 'react';
import { FileText, Download, Table as TableIcon } from 'lucide-react';
import { api } from '../../api';
import { useToast } from '../../context/ToastContext';
import type { ImageryAnalysis } from '../../types';

export const ReportsView: React.FC = () => {
  const [analyses, setAnalyses] = useState<ImageryAnalysis[]>([]);
  const { addToast } = useToast();

  useEffect(() => {
    api.analytics.getDashboardStats().then(data => {
      setAnalyses(data.recent_analyses);
    });
  }, []);

  const handleDownloadPdf = async (id: number) => {
    try {
      await api.reports.downloadPdf(id);
    } catch (e) {
      console.error(e);
      addToast('Failed to download PDF report. Please try again.', 'error');
    }
  };

  const handleDownloadCsv = async (id: number) => {
    try {
      await api.reports.downloadCsv(id);
    } catch (e) {
      console.error(e);
      addToast('Failed to download CSV feature data. Please try again.', 'error');
    }
  };

  const handleDownloadGeoJson = async (id: number) => {
    try {
      await api.reports.downloadGeoJson(id);
    } catch (e) {
      console.error(e);
      addToast('Failed to download GeoJSON. Please try again.', 'error');
    }
  };

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-5xl mx-auto space-y-6">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="text-blue-400" size={24} /> Executive Reports & Data Downloads
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Stream multi-page ReportLab PDF executive summaries and CSV vector feature summaries
        </p>
      </div>

      <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="p-3">Analysis ID</th>
                <th className="p-3">Filename</th>
                <th className="p-3">Population</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {analyses.map(item => (
                <tr key={item.id}>
                  <td className="p-3 font-mono font-semibold">#{item.id}</td>
                  <td className="p-3 font-medium text-white">{item.filename}</td>
                  <td className="p-3">{item.population_count !== null && item.population_count !== undefined ? `${item.population_count.toLocaleString()} Citizens` : 'Unavailable'}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      {item.status}
                    </span>
                  </td>
                  <td className="p-3 text-right space-x-2">
                    <button
                      onClick={() => handleDownloadPdf(item.id)}
                      disabled={item.status !== 'completed'}
                      className="px-2.5 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 border border-blue-500/30 rounded font-medium inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Download size={12} /> PDF Report
                    </button>
                    <button
                      onClick={() => handleDownloadCsv(item.id)}
                      disabled={item.status !== 'completed'}
                      className="px-2.5 py-1 bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 rounded font-medium inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <TableIcon size={12} /> CSV Features
                    </button>
                    <button
                      onClick={() => handleDownloadGeoJson(item.id)}
                      disabled={item.status !== 'completed'}
                      className="px-2.5 py-1 bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 rounded font-medium inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <TableIcon size={12} /> GeoJSON
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
