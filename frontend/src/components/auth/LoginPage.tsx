import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, Sparkles, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { api } from '../../api';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { addToast } = useToast();
  
  const [view, setView] = useState<'login' | 'register'>('login');
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  
  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLoginSubmit = async (e: React.FormEvent) => {
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

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await fetch('http://localhost:8000/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          role: 'planner'
        })
      }).then(async res => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Registration failed');
        }
      });
      
      addToast('Registration successful! You can now log in.', 'success');
      setView('login');
      setPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
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

        <form onSubmit={view === 'login' ? handleLoginSubmit : handleRegisterSubmit} className="space-y-4">
          {view === 'register' && (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name</label>
              <div className="relative">
                <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none transition-colors"
                  placeholder="John Doe"
                />
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size= {18} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none transition-colors"
                placeholder="you@example.com"
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
                autoComplete="current-password"
                className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-10 text-sm text-white focus:outline-none transition-colors"
                placeholder="Enter your password"
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

          {view === 'register' && (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2.5 pl-10 pr-10 text-sm text-white focus:outline-none transition-colors"
                  placeholder="Confirm your password"
                />
              </div>
            </div>
          )}

          {view === 'login' && (
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
                onClick={() => setShowRecoveryModal(true)}
                className="text-blue-400 hover:underline"
              >
                Forgot Password?
              </button>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm shadow-lg shadow-blue-600/20 mt-2"
          >
            {loading ? (view === 'login' ? 'Authenticating...' : 'Registering...') : (view === 'login' ? 'Sign In to Workspace' : 'Create Account')}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-400">
          {view === 'login' ? (
            <>
              Don't have an account?{' '}
              <button onClick={() => { setView('register'); setError(''); }} className="text-blue-400 hover:underline">
                Register Planner Account
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button onClick={() => { setView('login'); setError(''); }} className="text-blue-400 hover:underline">
                Sign In
              </button>
            </>
          )}
        </div>
      </div>

      {/* Password Recovery Modal */}
      {showRecoveryModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-2xl max-w-sm w-full space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-white">Password Recovery</h3>
            <p className="text-sm text-slate-400">
              Self-service password recovery is currently disabled. Please contact your system administrator to securely reset your account credentials.
            </p>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowRecoveryModal(false)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-blue-600/20"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
