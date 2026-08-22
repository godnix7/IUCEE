import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

/**
 * Gate for authenticated routes. While the session is being restored we show a spinner;
 * unauthenticated users are redirected to /login with the intended path preserved so they
 * can be returned there after signing in.
 */
export const ProtectedRoute: React.FC = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

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
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }

  return <Outlet />;
};
