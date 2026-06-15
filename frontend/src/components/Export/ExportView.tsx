import { useState } from 'react';
import { Download, FileArchive, CheckCircle } from 'lucide-react';
import { api } from '../../api';

export default function ExportView({ project }: { project: any }) {
  const [mode, setMode] = useState('reviewed');
  const [exporting, setExporting] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [error, setError] = useState('');

  const handleExport = async () => {
    if (!project) return;
    setExporting(true);
    setError('');
    setDownloadUrl('');
    
    try {
      const res = await api.exports.generate(project.id, mode);
      setDownloadUrl(`http://localhost:8000${res.download_url}`);
    } catch (err: any) {
      setError(err.message || 'Failed to generate export');
    } finally {
      setExporting(false);
    }
  };

  if (!project) return <div className="p-8">No project selected</div>;

  return (
    <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
      <h2 className="text-2xl font-bold mb-6">Export Dataset</h2>
      
      <div className="glass-panel p-8">
        <h3 className="text-lg font-medium mb-6 flex items-center gap-2">
          <Download className="text-primary" /> Configuration
        </h3>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm text-textMuted mb-3">Export Target</label>
            <div className="grid grid-cols-2 gap-4">
              <FormatOption 
                id="reviewed" 
                title="Reviewed Dataset" 
                desc="Includes all accepted, reviewed, and human-corrected images." 
                selected={mode === 'reviewed'}
                onClick={() => setMode('reviewed')}
              />
              <FormatOption 
                id="human_corrected" 
                title="Human-Corrected Only" 
                desc="Strictly filters for images that underwent manual polygon editing." 
                selected={mode === 'human_corrected'}
                onClick={() => setMode('human_corrected')}
              />
            </div>
          </div>
          
          {error && (
            <div className="text-red-400 text-sm p-3 bg-red-400/10 rounded border border-red-400/20">
              {error}
            </div>
          )}

          {downloadUrl && (
            <div className="flex items-center justify-between p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
              <div className="flex items-center gap-3 text-emerald-400">
                <CheckCircle size={20} />
                <span>Export generated successfully!</span>
              </div>
              <a 
                href={downloadUrl} 
                download 
                className="btn-primary px-4 py-2 flex items-center gap-2 text-sm"
              >
                <Download size={16} /> Download ZIP Archive
              </a>
            </div>
          )}

          <div className="pt-4 border-t border-white/10 flex justify-end">
            <button 
              onClick={handleExport}
              disabled={exporting}
              className="btn-primary px-8 py-3 text-lg w-full flex items-center justify-center gap-2"
            >
              {exporting ? (
                <span>Generating...</span>
              ) : (
                <>
                  <FileArchive size={20} /> Generate Dataset Archive
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FormatOption({ title, desc, selected, onClick, disabled = false }: any) {
  return (
    <div 
      onClick={disabled ? undefined : onClick}
      className={`p-4 rounded-lg border-2 transition-all ${
        disabled ? 'opacity-50 cursor-not-allowed border-white/5 bg-slate-900/50' :
        selected ? 'border-primary bg-primary/10 cursor-pointer' : 'border-white/10 bg-slate-900 cursor-pointer hover:border-white/30'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold">{title}</span>
        {selected && <CheckCircle size={16} className="text-primary" />}
      </div>
      <p className="text-xs text-textMuted">{desc}</p>
    </div>
  );
}
