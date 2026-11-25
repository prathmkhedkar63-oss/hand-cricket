import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Host } from '../types';
import { ShieldCheck, UserPlus, Trash2 } from 'lucide-react';

export const Hosts: React.FC = () => {
  const [hosts, setHosts] = useState<Host[]>([]);
  const [userId, setUserId] = useState('');
  const [username, setUsername] = useState('');
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    loadHosts();
  }, []);

  const loadHosts = async () => {
    try {
      const res = await api.getHosts();
      setHosts(res || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.assignHost({
        user_id: parseInt(userId),
        username,
        assigned_tournaments: ['*'],
      });
      setShowModal(false);
      setUserId('');
      setUsername('');
      loadHosts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRevoke = async (id: number) => {
    if (!confirm('Revoke host permissions for this user?')) return;
    try {
      await api.revokeHost(id);
      loadHosts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-bold text-white font-heading uppercase">
            Host Management
          </h3>
          <p className="text-xs text-slate-400">
            Designate tournament hosts authorized to manage specific championships
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-semibold rounded-lg text-xs uppercase tracking-wider font-heading transition"
        >
          <UserPlus className="w-4 h-4" />
          Assign Host
        </button>
      </div>

      <div className="bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-[#0a0d14] text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800 font-heading">
            <tr>
              <th className="px-6 py-3.5">Host Username</th>
              <th className="px-6 py-3.5">Telegram ID</th>
              <th className="px-6 py-3.5">Assigned Tournaments</th>
              <th className="px-6 py-3.5">Status</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {hosts.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  No hosts currently assigned.
                </td>
              </tr>
            ) : (
              hosts.map((h) => (
                <tr key={h.user_id} className="hover:bg-slate-800/30 transition">
                  <td className="px-6 py-4 font-medium text-white flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    @{h.username}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">
                    {h.user_id}
                  </td>
                  <td className="px-6 py-4 text-xs font-mono">
                    {h.assigned_tournaments?.join(', ') || 'All Tournaments'}
                  </td>
                  <td className="px-6 py-4">
                    {h.is_active ? (
                      <span className="px-2.5 py-1 text-xs rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-900/50">
                        Authorized
                      </span>
                    ) : (
                      <span className="px-2.5 py-1 text-xs rounded-full bg-red-950/40 text-red-400 border border-red-900/50">
                        Revoked
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {h.is_active && (
                      <button
                        onClick={() => handleRevoke(h.user_id)}
                        className="px-2.5 py-1 text-xs bg-red-950/30 text-red-400 border border-red-900/40 hover:bg-red-950/60 rounded transition"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white font-heading uppercase mb-4">
              Authorize New Host
            </h3>
            <form onSubmit={handleAssign} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Telegram User ID
                </label>
                <input
                  type="number"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  required
                  placeholder="e.g. 987654321"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Telegram Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="e.g. cricket_host"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Authorize
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
