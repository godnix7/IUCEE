import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Sparkles, CheckCircle2, Clock, FileText, AlertCircle, Play, Layers, ScanEye } from 'lucide-react';
import { api } from '../../api';
import type { Project, ImageryAnalysis } from '../../types';
import { useUploadQueue } from '../../context/UploadContext';

export const AnalysisWorkspace: React.FC<{ onNavigateMap: () => void }> = ({ onNavigateMap }) => {
  const {
    files, setFiles,
    populationCount, setPopulationCount,
    populationSource, setPopulationSource,
    populationDate, setPopulationDate,
    selectedProjectId, setSelectedProjectId,
    analysisMode, setAnalysisMode
  } = useUploadQueue();
  
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [uploading, setUploading] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<ImageryAnalysis | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.projects.list().then(projs => {
      setProjects(projs);
      if (projs.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projs[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (selectedProjectId) sessionStorage.setItem('selectedProjectId', selectedProjectId.toString());
  }, [selectedProjectId]);

  useEffect(() => {
    const savedId = sessionStorage.getItem('selectedAnalysisId');
    if (savedId) {
      api.inference.getStatus(Number(savedId)).then(setCurrentAnalysis).catch(console.error);
    }
  }, []);

  const handleUploadAndRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (files.length === 0 || !selectedProjectId) {
      setError('Please select a project and upload valid image files');
      return;
    }

    setError('');
    setUploading(true);
    try {
      let lastRes = null;
      for (const f of files) {
        if (!f.name.match(/\.(jpg|jpeg|png|tif|tiff|geotiff)$/i)) continue;
        lastRes = await api.inference.upload(
          selectedProjectId,
          f,
          populationCount === '' ? undefined : populationCount,
          populationSource,
          populationDate,
          analysisMode
        );
      }
      
      if (!lastRes) {
        throw new Error('No valid images found in selection.');
      }
      
      const analysis = await api.inference.getStatus(lastRes.analysis_id);
      setCurrentAnalysis(analysis);
      sessionStorage.setItem('selectedAnalysisId', analysis.id.toString());

      const interval = setInterval(async () => {
        try {
          const updated = await api.inference.getStatus(lastRes.analysis_id);
          setCurrentAnalysis(updated);
          if (updated.status === 'completed' || updated.status === 'failed') {
            clearInterval(interval);
          }
        } catch (e) {
          clearInterval(interval);
        }
      }, 3000);

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
          Choose an analysis mode, then upload imagery. Segmentation suits nadir (top-down) aerial/satellite; Detection suits oblique drone footage.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <form onSubmit={handleUploadAndRun} className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Analysis Mode</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <ModeCard
              active={analysisMode === 'segmentation'}
              onClick={() => setAnalysisMode('segmentation')}
              icon={<Layers size={18} />}
              title="Land-cover Segmentation"
              subtitle="Building / road / water / tree (LoveDA)"
              hint="Best for nadir aerial & satellite"
            />
            <ModeCard
              active={analysisMode === 'scene_segmentation'}
              onClick={() => setAnalysisMode('scene_segmentation')}
              icon={<Layers size={18} />}
              title="Scene Segmentation"
              subtitle="Road / building / tree / car / person (ADE20K)"
              hint="Best for oblique drone imagery"
            />
            <ModeCard
              active={analysisMode === 'detection'}
              onClick={() => setAnalysisMode('detection')}
              icon={<ScanEye size={18} />}
              title="Object Detection"
              subtitle="Vehicles & people (counts)"
              hint="Best for oblique drone footage"
            />
          </div>
        </div>

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
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Population (Optional)</label>
            <input
              type="number"
              value={populationCount}
              onChange={(e) => setPopulationCount(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="Leave blank if unknown"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Population Source</label>
            <input
              type="text"
              value={populationSource}
              onChange={(e) => setPopulationSource(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Population Date</label>
            <input
              type="date"
              value={populationDate}
              onChange={(e) => setPopulationDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="border-2 border-dashed border-slate-700 hover:border-blue-500/50 rounded-xl p-8 text-center transition-colors">
          <Upload className="mx-auto text-blue-400 mb-3" size={32} />
          <h4 className="text-sm font-semibold text-white mb-1">
            {files.length > 0 ? `${files.length} file(s) selected` : 'Select or Drop GeoTIFF / Satellite Images or Folder'}
          </h4>
          <p className="text-xs text-slate-500 mb-4">Supported Formats: .geotiff, .tif, .png, .jpg</p>

          <input
            type="file"
            id="file-upload"
            multiple
            accept=".geotiff,.tif,.tiff,.png,.jpg,.jpeg"
            onChange={(e) => {
              if (e.target.files) setFiles(Array.from(e.target.files));
            }}
            className="hidden"
          />
          <div className="flex justify-center gap-3">
            <label
              htmlFor="file-upload"
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium cursor-pointer border border-slate-700"
            >
              Browse Files or Folder
            </label>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('file-upload') as HTMLInputElement;
                if (el) {
                  el.removeAttribute('webkitdirectory');
                  el.removeAttribute('directory');
                  el.click();
                  setTimeout(() => {
                    el.setAttribute('webkitdirectory', 'true');
                    el.setAttribute('directory', 'true');
                  }, 100);
                }
              }}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium cursor-pointer border border-slate-700"
            >
              Browse Files Only
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={uploading || files.length === 0}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-medium text-xs flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
        >
          {uploading
            ? 'Uploading & queuing…'
            : analysisMode === 'detection'
              ? 'Run Object Detection Pipeline'
              : analysisMode === 'scene_segmentation'
                ? 'Run Scene Segmentation Pipeline'
                : 'Run Land-cover Segmentation Pipeline'}
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
            {(currentAnalysis.analysis_mode === 'detection') ? (
              <>
                <StatusStep title="File Upload & Validation" done={true} />
                <StatusStep title="COCO Object Detection Inference (vehicles / people)" done={currentAnalysis.status === 'completed'} />
                <StatusStep title="Annotated Overlay & Detection Summary" done={currentAnalysis.status === 'completed'} />
              </>
            ) : (
              <>
                <StatusStep title="File Upload & Coordinate Validation" done={true} />
                <StatusStep title="SegFormer PyTorch Pretrained Inference" done={currentAnalysis.status === 'completed'} />
                <StatusStep title="OpenStreetMap Layer Enrichment (Schools/Hospitals/Slums)" done={currentAnalysis.status === 'completed'} />
                <StatusStep title="Urban Metrics & Benchmark Score Calculation" done={currentAnalysis.status === 'completed'} />
              </>
            )}
          </div>

          {currentAnalysis.status === 'completed' && currentAnalysis.analysis_mode === 'detection' && (
            <DetectionResults analysis={currentAnalysis} />
          )}

          {currentAnalysis.status === 'completed' && (
            <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
              <button
                onClick={() => navigate(`/analyses/${currentAnalysis.id}/review`)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg flex items-center gap-2 shadow-lg shadow-blue-600/20"
              >
                <ScanEye size={14} /> Review AI Detections
              </button>
              {currentAnalysis.analysis_mode !== 'detection' && (
                <button
                  onClick={onNavigateMap}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg flex items-center gap-2 shadow-lg shadow-emerald-600/20"
                >
                  <Play size={14} /> Open GIS Explorer Map
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ModeCard: React.FC<{
  active: boolean; onClick: () => void; icon: React.ReactNode;
  title: string; subtitle: string; hint: string;
}> = ({ active, onClick, icon, title, subtitle, hint }) => (
  <button
    type="button"
    onClick={onClick}
    className={`text-left p-3 rounded-xl border transition-colors ${
      active
        ? 'bg-blue-500/10 border-blue-500/60 ring-1 ring-blue-500/40'
        : 'bg-slate-900 border-slate-700 hover:border-slate-600'
    }`}
  >
    <div className="flex items-center gap-2">
      <span className={active ? 'text-blue-400' : 'text-slate-400'}>{icon}</span>
      <span className="text-xs font-semibold text-white">{title}</span>
      {active && <CheckCircle2 size={14} className="text-blue-400 ml-auto" />}
    </div>
    <p className="text-[11px] text-slate-300 mt-1.5">{subtitle}</p>
    <p className="text-[10px] text-slate-500 mt-0.5">{hint}</p>
  </button>
);

const DetectionResults: React.FC<{ analysis: ImageryAnalysis }> = ({ analysis }) => {
  const [overlayUrl, setOverlayUrl] = useState<string | null>(null);
  const [imgErr, setImgErr] = useState(false);
  const summary = analysis.detection_summary;

  useEffect(() => {
    let revoked: string | null = null;
    api.inference
      .getDetectionOverlayUrl(analysis.id)
      .then((url) => { revoked = url; setOverlayUrl(url); })
      .catch(() => setImgErr(true));
    return () => { if (revoked) URL.revokeObjectURL(revoked); };
  }, [analysis.id]);

  const counts = summary?.class_counts || {};
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  return (
    <div className="pt-4 border-t border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-white flex items-center gap-2">
          <ScanEye size={14} className="text-blue-400" /> Detection Results
        </h4>
        <span className="text-[10px] text-slate-500">{summary?.model}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="px-2.5 py-1 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-300 border border-blue-500/30">
          {summary?.total_detections ?? 0} total objects
        </span>
        {entries.map(([cls, n]) => (
          <span key={cls} className="px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-800 text-slate-200 border border-slate-700">
            {cls}: {n}
          </span>
        ))}
      </div>

      {!summary?.geo_referenced && (
        <p className="text-[10px] text-amber-400/80 flex items-center gap-1">
          <AlertCircle size={11} /> Image is not georeferenced — results are shown on the image, not the map.
        </p>
      )}

      {overlayUrl && !imgErr ? (
        <img
          src={overlayUrl}
          alt="Detection overlay"
          onError={() => setImgErr(true)}
          className="w-full rounded-xl border border-slate-800"
        />
      ) : imgErr ? (
        <p className="text-xs text-slate-500">Overlay image unavailable.</p>
      ) : (
        <p className="text-xs text-slate-500">Loading overlay…</p>
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
