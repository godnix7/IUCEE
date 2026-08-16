import React, { useState, useEffect } from 'react';
import { Upload, Sparkles, CheckCircle2, Clock, FileText, AlertCircle, Play } from 'lucide-react';
import { api } from '../../api';
import type { Project, ImageryAnalysis } from '../../types';

export const AnalysisWorkspace: React.FC<{ onNavigateMap: () => void }> = ({ onNavigateMap }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [population, setPopulation] = useState(1000);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<ImageryAnalysis | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.projects.list().then(projs => {
      setProjects(projs);
      if (projs.length > 0) setSelectedProjectId(projs[0].id);
    });
  }, []);

  const handleUploadAndRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedProjectId) {
      setError('Please select a project and upload a valid image file');
      return;
    }

    setError('');
    setUploading(true);
    try {
      const analysis = await api.inference.upload(selectedProjectId, file, population);
      setCurrentAnalysis(analysis);

      const updated = await api.inference.run(analysis.id);
      setCurrentAnalysis(updated);
    } catch (err: any) {
      setError(err.message || 'Analysis processing failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-4xl mx-auto space-y-6">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Sparkles className="text-blue-400" size={24} /> AI Analysis Workspace
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Upload satellite imagery or drone orthomosaics for pretrained aerial SegFormer inference
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <form onSubmit={handleUploadAndRun} className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Target Project</label>
            <select
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none"
            >
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Estimated Citizen Population</label>
            <input
              type="number"
              value={population}
              onChange={(e) => setPopulation(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none"
            />
          </div>
        </div>

        <div className="border-2 border-dashed border-slate-700 hover:border-blue-500/50 rounded-xl p-8 text-center transition-colors">
          <Upload className="mx-auto text-blue-400 mb-3" size={32} />
          <h4 className="text-sm font-semibold text-white mb-1">
            {file ? file.name : 'Select or Drop GeoTIFF / Satellite Image'}
          </h4>
          <p className="text-xs text-slate-500 mb-4">Supported Formats: .geotiff, .tif, .png, .jpg (Max 500MB)</p>

          <input
            type="file"
            id="file-upload"
            onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
            className="hidden"
          />
          <label
            htmlFor="file-upload"
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium cursor-pointer border border-slate-700"
          >
            Browse Imagery File
          </label>
        </div>

        <button
          type="submit"
          disabled={uploading || !file}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-medium text-xs flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
        >
          {uploading ? 'Processing AI Segmentation & OSM Enrichment...' : 'Run AI Imagery Segmentation Pipeline'}
        </button>
      </form>

      {currentAnalysis && (
        <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <FileText className="text-blue-400" size={16} /> Processing Status: Analysis #{currentAnalysis.id}
            </h3>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
              currentAnalysis.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
            }`}>
              {currentAnalysis.status}
            </span>
          </div>

          <div className="space-y-3">
            <StatusStep title="File Upload & Coordinate Validation" done={true} />
            <StatusStep title="SegFormer PyTorch Pretrained Inference" done={currentAnalysis.status === 'completed'} />
            <StatusStep title="OpenStreetMap Layer Enrichment (Schools/Hospitals/Slums)" done={currentAnalysis.status === 'completed'} />
            <StatusStep title="Urban Metrics & Benchmark Score Calculation" done={currentAnalysis.status === 'completed'} />
          </div>

          {currentAnalysis.status === 'completed' && (
            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={onNavigateMap}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg flex items-center gap-2 shadow-lg shadow-emerald-600/20"
              >
                <Play size={14} /> Open GIS Explorer Map
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const StatusStep: React.FC<{ title: string; done: boolean }> = ({ title, done }) => (
  <div className="flex items-center gap-3">
    {done ? (
      <CheckCircle2 className="text-emerald-400" size={18} />
    ) : (
      <Clock className="text-slate-500 animate-spin" size={18} />
    )}
    <span className={`text-xs ${done ? 'text-slate-200 font-medium' : 'text-slate-500'}`}>{title}</span>
  </div>
);
