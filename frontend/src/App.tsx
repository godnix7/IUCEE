import { useEffect, useState } from 'react';
import { BarChart3, Download, Eye, Layers, Upload } from 'lucide-react';
import { api } from './api';

import DashboardView from './components/Dashboard/DashboardView';
import ExportView from './components/Export/ExportView';
import ImportView from './components/Import/ImportView';
import ReviewView from './components/Review/ReviewView';

function App() {
  const [activeTab, setActiveTab] = useState('import');
  const [currentProject, setCurrentProject] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [showSessionRecovery, setShowSessionRecovery] = useState(false);
  const [savedSession, setSavedSession] = useState<{ projectId: number; tab: string } | null>(null);

  useEffect(() => {
    if (!currentProject) return;

    const fetchStats = async () => {
      try {
        const data = await api.dashboard.getStats(currentProject.id);
        setStats(data);
      } catch (err) {
        console.error(err);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [currentProject]);

  useEffect(() => {
    const savedProjectId = localStorage.getItem('currentProjectId');
    const savedTab = localStorage.getItem('activeTab');

    api.projects.list().then((projects) => {
      if (projects.length === 0) return;

      if (savedProjectId) {
        const matchedProject = projects.find((project: any) => project.id === parseInt(savedProjectId));
        if (matchedProject) {
          setSavedSession({ projectId: matchedProject.id, tab: savedTab || 'dashboard' });
          setShowSessionRecovery(true);
          return;
        }
      }

      setCurrentProject(projects[projects.length - 1]);
      setActiveTab('dashboard');
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (currentProject) {
      localStorage.setItem('currentProjectId', currentProject.id.toString());
      localStorage.setItem('activeTab', activeTab);
    }
  }, [currentProject, activeTab]);

  const resumeSession = () => {
    if (!savedSession) return;
    api.projects.get(savedSession.projectId).then((project) => {
      setCurrentProject(project);
      setActiveTab(savedSession.tab);
      setShowSessionRecovery(false);
    });
  };

  const startNewSession = () => {
    localStorage.removeItem('currentProjectId');
    localStorage.removeItem('activeTab');
    setShowSessionRecovery(false);
    api.projects.list().then((projects) => {
      if (projects.length > 0) {
        setCurrentProject(projects[projects.length - 1]);
        setActiveTab('dashboard');
      } else {
        setActiveTab('import');
      }
    });
  };

  const handleAutoLabelAll = async () => {
    if (!currentProject) return;
    try {
      await api.labeling.autoLabelAll(currentProject.id);
      setActiveTab('dashboard');
    } catch (err) {
      alert('Failed to start auto-labeling: ' + err);
    }
  };

  const processedPercent = stats?.total_images
    ? Math.round((stats.processed_images / stats.total_images) * 100)
    : 0;

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-background text-textMain">
      <nav className="w-16 flex flex-col items-center py-5 border-r border-white/10 bg-[#101827] z-10">
        <button
          className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center mb-7 shadow-lg shadow-black/20"
          onClick={() => window.location.reload()}
          title="Reload"
        >
          <Layers className="text-white" size={20} />
        </button>

        <div className="flex flex-col gap-4 mt-4 w-full px-2">
          <NavButton
            icon={<Upload size={22} />}
            isActive={activeTab === 'import'}
            onClick={() => setActiveTab('import')}
            tooltip="Dataset"
          />
          {currentProject && (
            <>
              <NavButton
                icon={<BarChart3 size={22} />}
                isActive={activeTab === 'dashboard'}
                onClick={() => setActiveTab('dashboard')}
                tooltip="Dashboard"
              />
              <NavButton
                icon={<Eye size={22} />}
                isActive={activeTab === 'review'}
                onClick={() => setActiveTab('review')}
                tooltip="Human Review"
              />
              <div className="h-px bg-white/10 w-full my-2"></div>
              <NavButton
                icon={<Download size={22} />}
                isActive={activeTab === 'export'}
                onClick={() => setActiveTab('export')}
                tooltip="Export"
              />
            </>
          )}
        </div>
      </nav>

      <main className="flex-1 flex flex-col relative overflow-hidden">
        <header className="h-16 border-b border-white/10 bg-[#111b2b]/95 flex items-center px-6 justify-between z-10">
          <div>
            <h1 className="font-semibold text-lg">
              {currentProject ? `Project: ${currentProject.name}` : 'Setup New Project'}
            </h1>
            {stats && (
              <p className="text-xs text-textMuted">
                {stats.total_images} images | {Object.keys(stats.class_distribution || {}).length} classes | {processedPercent}% processed
              </p>
            )}
          </div>

          {currentProject && (
            <button onClick={handleAutoLabelAll} className="btn-primary flex items-center gap-2 text-sm">
              <Layers size={16} /> Auto-Label All
            </button>
          )}
        </header>

        <div className="flex-1 overflow-auto bg-background relative flex">
          {activeTab === 'import' && (
            <ImportView onProjectCreated={(project: any) => { setCurrentProject(project); setActiveTab('dashboard'); }} />
          )}
          {activeTab === 'dashboard' && currentProject && (
            <DashboardView
              project={currentProject}
              stats={stats}
              onStatsUpdate={() => api.dashboard.getStats(currentProject.id).then(setStats)}
            />
          )}
          {activeTab === 'review' && currentProject && <ReviewView project={currentProject} />}
          {activeTab === 'export' && currentProject && <ExportView project={currentProject} />}
        </div>
      </main>

      {showSessionRecovery && (
        <div className="fixed inset-0 z-[200] bg-black/80 backdrop-blur-md flex items-center justify-center">
          <div className="bg-slate-900 border border-white/10 rounded-lg p-8 max-w-md w-full shadow-2xl">
            <h2 className="text-xl font-bold text-white mb-2">Session Recovery</h2>
            <p className="text-textMuted mb-6">
              An active labeling session was found. Would you like to resume where you left off?
            </p>
            <div className="flex gap-4">
              <button
                onClick={startNewSession}
                className="flex-1 py-3 px-4 rounded-lg bg-white/5 hover:bg-white/10 text-white font-medium transition-colors"
              >
                Start New Session
              </button>
              <button
                onClick={resumeSession}
                className="flex-1 py-3 px-4 rounded-lg bg-primary hover:bg-blue-600 text-white font-medium transition-colors"
              >
                Resume Session
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NavButton({ icon, isActive, onClick, tooltip }: any) {
  return (
    <button
      onClick={onClick}
      className={`relative w-full aspect-square flex items-center justify-center rounded-lg transition-all duration-200 ${
        isActive ? 'bg-primary/10 text-primary' : 'text-textMuted hover:text-white hover:bg-white/5'
      }`}
      title={tooltip}
    >
      {isActive && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-r-full"></div>
      )}
      {icon}
    </button>
  );
}

export default App;
