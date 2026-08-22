import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/** Restricts a route to specific roles, rendering a clear forbidden state otherwise. */
export const RoleRoute: React.FC<{ roles: string[]; children: React.ReactNode }> = ({ roles, children }) => {
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user || !roles.includes(user.role)) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#0b0f19] text-slate-300 gap-3 p-8 text-center">
        <ShieldAlert size={40} className="text-amber-500" />
        <div className="text-sm font-semibold text-white">Access restricted</div>
        <div className="text-xs text-slate-400 max-w-sm">
          This section is available to {roles.join(' / ')} roles only. Your role
          {user ? ` (${user.role})` : ''} does not have access.
        </div>
        <button onClick={() => navigate('/dashboard')} className="mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs">
          Back to Dashboard
        </button>
      </div>
    );
  }

  return <>{children}</>;
};
