import React, { useState } from 'react';
import {
  BarChart3, Compass, Upload, FileText, Settings, Users, LogOut, Sparkles, Building
} from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { LoginPage } from './components/auth/LoginPage';
import { DashboardView } from './components/dashboard/DashboardView';
import { GisExplorerView } from './components/map/GisExplorerView';
import { AnalysisWorkspace } from './components/analysis/AnalysisWorkspace';
import { BenchmarkView } from './components/benchmarks/BenchmarkView';
import { ReportsView } from './components/reports/ReportsView';
import { SettingsView } from './components/settings/SettingsView';
import { UsersView } from './components/users/UsersView';

function AppContent() {
  const { user, loading, logout, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'map' | 'analysis' | 'benchmarks' | 'reports' | 'users' | 'settings'>('dashboard');

  if (loading) {
    return (
      <div className="h-screen w-screen bg-[#0b0f19] text-white flex items-center justify-center">
        <div className="flex items-center gap-3 text-blue-400">
          <Sparkles className="animate-spin" size={24} />
          <span>Initializing UrbanSense Intelligence Platform...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage onNavigateRegister={() => {}} onNavigateForgot={() => {}} />;
  }

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#0b0f19] text-slate-100 font-sans">
      <nav className="w-16 flex flex-col items-center py-5 border-r border-slate-800 bg-[#101827] z-20">
        <button
          onClick={() => setActiveTab('dashboard')}
          className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center mb-6 shadow-lg shadow-blue-600/30 text-white"
          title="UrbanSense Dashboard"
        >
          <Sparkles size={20} />
        </button>

        <div className="flex flex-col gap-3 w-full px-2 flex-1">
          <NavBtn icon={<BarChart3 size={20} />} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
          <NavBtn icon={<Compass size={20} />} label="GIS Explorer" active={activeTab === 'map'} onClick={() => setActiveTab('map')} />
          <NavBtn icon={<Upload size={20} />} label="AI Workspace" active={activeTab === 'analysis'} onClick={() => setActiveTab('analysis')} />
          <NavBtn icon={<Building size={20} />} label="Benchmarks" active={activeTab === 'benchmarks'} onClick={() => setActiveTab('benchmarks')} />
          <NavBtn icon={<FileText size={20} />} label="Reports" active={activeTab === 'reports'} onClick={() => setActiveTab('reports')} />
          {isAdmin && (
            <NavBtn icon={<Users size={20} />} label="User Admin" active={activeTab === 'users'} onClick={() => setActiveTab('users')} />
          )}
        </div>

        <div className="flex flex-col gap-3 w-full px-2">
          <NavBtn icon={<Settings size={20} />} label="Settings" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
          <button
            onClick={logout}
            className="w-full aspect-square flex items-center justify-center rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Sign Out"
          >
            <LogOut size={20} />
          </button>
        </div>
      </nav>

      <main className="flex-1 flex flex-col relative overflow-hidden">
        {activeTab === 'dashboard' && (
          <DashboardView onNavigateMap={() => setActiveTab('map')} onNavigateAnalysis={() => setActiveTab('analysis')} />
        )}
        {activeTab === 'map' && (
          <GisExplorerView onNavigateUpload={() => setActiveTab('analysis')} />
        )}
        {activeTab === 'analysis' && (
          <AnalysisWorkspace onNavigateMap={() => setActiveTab('map')} />
        )}
        {activeTab === 'benchmarks' && <BenchmarkView />}
        {activeTab === 'reports' && <ReportsView />}
        {activeTab === 'users' && <UsersView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  );
}

function NavBtn({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`relative w-full aspect-square flex items-center justify-center rounded-xl transition-all ${
        active
          ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-lg shadow-blue-500/10'
          : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
      }`}
      title={label}
    >
      {active && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />
      )}
      {icon}
    </button>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ToastProvider>
  );
}
