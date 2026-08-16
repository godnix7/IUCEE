import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, Shield, Sparkles } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const LoginPage: React.FC<{ onNavigateRegister: () => void; onNavigateForgot: () => void }> = ({
  onNavigateRegister,
  onNavigateForgot
}) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('planner@urbansense.ai');
  const [password, setPassword] = useState('planner123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  const setDemoRole = (roleEmail: string, rolePass: string) => {
    setEmail(roleEmail);
    setPassword(rolePass);
  };

  return (
    <div className="min-h-screen w-full bg-[#0b0f19] text-white flex items-center justify-center p-4 relative overflow-hidden">
      {/* Dynamic Background Glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-600/20 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-[#111827]/90 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-xl p-8 z-10">
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="p-3 bg-blue-600/20 border border-blue-500/30 rounded-xl text-blue-400">
            <Sparkles size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">UrbanSense</h1>
            <p className="text-xs text-slate-400">AI Powered GIS Infrastructure Intelligence</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size= {18} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none transition-colors"
                placeholder="name@organization.gov"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-10 text-sm text-white focus:outline-none transition-colors"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
              />
              Remember me
            </label>
            <button
              type="button"
              onClick={onNavigateForgot}
              className="text-blue-400 hover:underline"
            >
              Forgot Password?
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm shadow-lg shadow-blue-600/20"
          >
            {loading ? 'Authenticating...' : 'Sign In to Workspace'}
          </button>
        </form>

        {/* Quick Role Selector */}
        <div className="mt-6 pt-6 border-t border-slate-800">
          <p className="text-xs text-slate-400 text-center mb-3 flex items-center justify-center gap-1">
            <Shield size={14} className="text-slate-500" /> Select Authentication Role:
          </p>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setDemoRole('admin@urbansense.ai', 'admin123')}
              className="py-1.5 text-xs bg-slate-800 hover:bg-slate-700 rounded text-slate-300 border border-slate-700 transition-colors"
            >
              Admin
            </button>
            <button
              type="button"
              onClick={() => setDemoRole('planner@urbansense.ai', 'planner123')}
              className="py-1.5 text-xs bg-blue-900/40 hover:bg-blue-900/60 rounded text-blue-300 border border-blue-700/50 transition-colors"
            >
              Planner
            </button>
            <button
              type="button"
              onClick={() => setDemoRole('viewer@urbansense.ai', 'viewer123')}
              className="py-1.5 text-xs bg-slate-800 hover:bg-slate-700 rounded text-slate-300 border border-slate-700 transition-colors"
            >
              Viewer
            </button>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-slate-400">
          Don't have an account?{' '}
          <button onClick={onNavigateRegister} className="text-blue-400 hover:underline">
            Register Planner Account
          </button>
        </div>
      </div>
    </div>
  );
};
