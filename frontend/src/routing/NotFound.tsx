import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Compass } from 'lucide-react';

export const NotFound: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-[#0b0f19] text-slate-300 gap-3 p-8 text-center">
      <div className="text-5xl font-bold text-slate-700">404</div>
      <Compass size={28} className="text-slate-600" />
      <div className="text-sm font-semibold text-white">Page not found</div>
      <div className="text-xs text-slate-500 font-mono">{location.pathname}</div>
      <button onClick={() => navigate('/dashboard')} className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs">
        Back to Dashboard
      </button>
    </div>
  );
};
