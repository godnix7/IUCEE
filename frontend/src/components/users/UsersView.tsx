import React, { useEffect, useState } from 'react';
import { Users as UsersIcon } from 'lucide-react';
import { api } from '../../api';
import type { User } from '../../types';

export const UsersView: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    api.users.list().then(setUsers).catch(console.error);
  }, []);

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <UsersIcon className="text-blue-400" size={24} /> Admin User Management
          </h1>
          <p className="text-xs text-slate-400 mt-1">Manage system accounts, roles (Admin, Planner, Viewer), and authorization</p>
        </div>
      </div>

      <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="p-3">User ID</th>
                <th className="p-3">Email Address</th>
                <th className="p-3">Full Name</th>
                <th className="p-3">Role</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {users.map(u => (
                <tr key={u.id}>
                  <td className="p-3 font-mono font-semibold">#{u.id}</td>
                  <td className="p-3 font-medium text-white">{u.email}</td>
                  <td className="p-3">{u.full_name || 'N/A'}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      u.role === 'admin' ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' :
                      u.role === 'planner' ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' :
                      'bg-slate-800 text-slate-400 border-slate-700'
                    }`}>
                      {u.role.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
