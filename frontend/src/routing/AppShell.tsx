import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, Compass, Upload, FileText, Settings, Users, LogOut, Sparkles, Building, ListChecks } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

/** Authenticated app chrome: left nav rail + routed content via <Outlet/>. */
export const AppShell: React.FC = () => {
  const { logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname;
  const isActive = (p: string) => path === p || path.startsWith(p + '/');

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#0b0f19] text-slate-100 font-sans">
      <nav className="w-16 flex flex-col items-center py-5 border-r border-slate-800 bg-[#101827] z-20">
        <button
          onClick={() => navigate('/dashboard')}
          className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center mb-6 shadow-lg shadow-blue-600/30 text-white"
          title="UrbanSense Dashboard"
        >
          <Sparkles size={20} />
        </button>

        <div className="flex flex-col gap-3 w-full px-2 flex-1">
          <NavBtn icon={<BarChart3 size={20} />} label="Dashboard" active={isActive('/dashboard')} onClick={() => navigate('/dashboard')} />
          <NavBtn icon={<Compass size={20} />} label="GIS Explorer" active={isActive('/map')} onClick={() => navigate('/map')} />
          <NavBtn icon={<Upload size={20} />} label="AI Workspace" active={isActive('/upload')} onClick={() => navigate('/upload')} />
          <NavBtn icon={<ListChecks size={20} />} label="Jobs" active={isActive('/jobs')} onClick={() => navigate('/jobs')} />
          <NavBtn icon={<Building size={20} />} label="Benchmarks" active={isActive('/benchmarks')} onClick={() => navigate('/benchmarks')} />
          <NavBtn icon={<FileText size={20} />} label="Reports" active={isActive('/reports')} onClick={() => navigate('/reports')} />
          {isAdmin && (
            <NavBtn icon={<Users size={20} />} label="User Admin" active={isActive('/admin')} onClick={() => navigate('/admin/users')} />
          )}
        </div>

        <div className="flex flex-col gap-3 w-full px-2">
          <NavBtn icon={<Settings size={20} />} label="Settings" active={isActive('/settings')} onClick={() => navigate('/settings')} />
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
        <Outlet />
      </main>
    </div>
  );
};

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
      {active && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />}
      {icon}
    </button>
  );
}
