import React from 'react';
import { Settings as SettingsIcon, User as UserIcon, Cpu } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const SettingsView: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-4xl mx-auto space-y-6">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon className="text-blue-400" size={24} /> System & Profile Settings
        </h1>
        <p className="text-xs text-slate-400 mt-1">Configure AI model thresholds, user preferences, and security settings</p>
      </div>

      <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-slate-800 pb-2">
            <UserIcon size={16} className="text-blue-400" /> Authenticated Profile
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Full Name</label>
              <input type="text" value={user?.full_name || 'System User'} disabled className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-300" />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Email Address</label>
              <input type="text" value={user?.email || ''} disabled className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-300" />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Assigned Role</label>
              <input type="text" value={user?.role?.toUpperCase() || ''} disabled className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-blue-400 font-bold" />
            </div>
          </div>
        </div>

        <div className="space-y-4 pt-4 border-t border-slate-800">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-slate-800 pb-2">
            <Cpu size={16} className="text-cyan-400" /> Pretrained SegFormer AI Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Model Architecture</label>
              <input type="text" value="wu-pr-gw/segformer-b2-finetuned-with-LoveDA" disabled className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-300 font-mono" />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Confidence Score Threshold</label>
              <input type="text" value="0.75 Minimum Confidence" disabled className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-slate-300" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
