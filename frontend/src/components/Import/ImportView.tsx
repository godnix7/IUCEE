import React, { useState } from 'react';
import { Upload, Folder } from 'lucide-react';
import { api } from '../../api';

export default function ImportView({ onProjectCreated }: { onProjectCreated: (p: any) => void }) {
  const [name, setName] = useState('');
  const [path, setPath] = useState('C:\\Nischay\\PROJECTS\\IUCEEE\\Dataset'); // Default placeholder
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !path) {
      setError('Name and Folder Path are required');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const project = await api.projects.create({
        name,
        description: 'Auto-imported dataset',
        root_path: path,
        classes: []
      });
      onProjectCreated(project);
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 p-8 max-w-4xl mx-auto w-full overflow-y-auto">
      <h2 className="text-2xl font-bold mb-6">Create New Project</h2>
      
      {error && (
        <div className="bg-red-500/20 border border-red-500/50 text-red-200 p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="glass-panel p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center gap-2">
            <Folder size={20} className="text-primary" /> Dataset Location
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-textMuted mb-1">Project Name</label>
              <input 
                type="text" 
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-4 py-2 focus:border-primary outline-none"
                placeholder="e.g. Aerial Imagery 2026"
              />
            </div>
            
            <div>
              <label className="block text-sm text-textMuted mb-1">Absolute Folder Path (Server-side)</label>
              <div className="flex gap-2">
                <input 
                  type="text" 
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  className="flex-1 bg-slate-900 border border-white/10 rounded-lg px-4 py-2 focus:border-primary outline-none font-mono text-sm"
                  placeholder="C:\path\to\your\images"
                />
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const res = await api.projects.selectFolder();
                      if (res.path) setPath(res.path);
                    } catch (err) {
                      console.error(err);
                    }
                  }}
                  className="bg-slate-800 border border-white/10 hover:border-primary/50 text-white px-4 py-2 rounded-lg flex items-center gap-2"
                >
                  <Folder size={18} /> Select Folder
                </button>
              </div>
              <p className="text-xs text-textMuted mt-2">
                The backend will recursively scan this folder for all supported images (jpg, png, tif, etc).
              </p>
            </div>
          </div>
        </div>

        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium flex items-center gap-2">
              <Upload size={20} className="text-accent" /> Fixed Aerial Ontology
            </h3>
          </div>
          <p className="text-sm text-textMuted mb-4">
            The system uses a strictly defined schema for production-quality aerial segmentation. 
            Supported classes include roads, buildings, schools, hospitals, substations, water assets, vegetation, vehicles, sidewalks, bare ground, shadows, and construction areas.
          </p>
        </div>

        <div className="flex justify-end">
          <button 
            type="submit" 
            disabled={loading}
            className={`btn-primary px-8 py-3 text-lg ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'Scanning Directory...' : 'Create & Scan Dataset'}
          </button>
        </div>
      </form>
    </div>
  );
}
