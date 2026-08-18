import React, { useEffect, useState } from 'react';
import { Plus, Users as UsersIcon } from 'lucide-react';
import { api } from '../../api';
import { useToast } from '../../context/ToastContext';
import type { User } from '../../types';

export const UsersView: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({ email: '', full_name: '', password: '', role: 'planner' });
  const { addToast } = useToast();

  const fetchUsers = () => {
    api.users.list().then(setUsers).catch((err) => {
      console.error(err);
      addToast('Failed to load user management list.', 'error');
    });
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.users.create(formData);
      addToast('User created successfully.', 'success');
      setShowForm(false);
      setFormData({ email: '', full_name: '', password: '', role: 'planner' });
      fetchUsers();
    } catch (err: any) {
      console.error(err);
      addToast(err.message || 'Failed to create user.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 bg-[#0b0f19] text-white p-6 overflow-y-auto max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <UsersIcon className="text-blue-400" size={24} /> Admin User Management
          </h1>
          <p className="text-xs text-slate-400 mt-1">Manage system accounts, roles (Admin, Planner, Viewer), and authorization</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium flex items-center gap-2"
        >
          <Plus size={16} /> New User
        </button>
      </div>

      {showForm && (
        <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-xl animate-in fade-in slide-in-from-top-2">
          <h3 className="text-lg font-bold text-white mb-4">Create System User</h3>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2 px-3 text-sm text-white focus:outline-none"
                  placeholder="Jane Doe"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2 px-3 text-sm text-white focus:outline-none"
                  placeholder="jane@example.com"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Initial Password</label>
                <input
                  type="password"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2 px-3 text-sm text-white focus:outline-none"
                  placeholder="Minimum 8 characters"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">System Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 rounded-lg py-2 px-3 text-sm text-white focus:outline-none"
                >
                  <option value="viewer">Viewer (Read-only)</option>
                  <option value="planner">Planner (Standard)</option>
                  <option value="admin">Admin (Full Access)</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </div>
      )}

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
