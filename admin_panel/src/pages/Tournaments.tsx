import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Tournament } from '../types';
import { Trophy, Plus, Users, Shield, Trash2 } from 'lucide-react';

export const Tournaments: React.FC = () => {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState<'solo' | 'host'>('solo');
  const [groupId, setGroupId] = useState('-1001234567890');
  const [selectedTournament, setSelectedTournament] = useState<Tournament | null>(null);
  const [participants, setParticipants] = useState<any[]>([]);

  useEffect(() => {
    loadTournaments();
  }, []);

  const loadTournaments = async () => {
    try {
      const res = await api.getTournaments();
      setTournaments(res || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createTournament({
        name,
        description,
        mode,
        group_chat_id: parseInt(groupId),
        max_balls: 36,
      });
      setShowCreateModal(false);
      setName('');
      setDescription('');
      loadTournaments();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to archive this tournament?')) return;
    try {
      await api.deleteTournament(id);
      loadTournaments();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const viewParticipants = async (t: Tournament) => {
    setSelectedTournament(t);
    try {
      const res = await api.getTournamentParticipants(t.tournament_id);
      setParticipants(res || []);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-bold text-white font-heading uppercase">
            Tournament Management
          </h3>
          <p className="text-xs text-slate-400">
            Control automated Solo championships and Host-managed events
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-semibold rounded-lg text-xs uppercase tracking-wider font-heading transition"
        >
          <Plus className="w-4 h-4" />
          Create Tournament
        </button>
      </div>

      {/* Tournaments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tournaments.map((t) => (
          <div
            key={t.tournament_id}
            className="bg-[#0f1422] border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between"
          >
            <div>
              <div className="flex justify-between items-start mb-3">
                <span className={`px-2.5 py-0.5 text-[11px] rounded font-semibold uppercase tracking-wider ${
                  t.mode === 'solo' ? 'bg-purple-950/40 text-purple-400 border border-purple-900/50' : 'bg-sky-950/40 text-sky-400 border border-sky-900/50'
                }`}>
                  {t.mode} mode
                </span>
                <span className="text-xs text-slate-400 uppercase font-mono">
                  {t.status}
                </span>
              </div>
              <h4 className="text-base font-bold text-white font-heading">
                {t.name}
              </h4>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                {t.description || 'No description provided.'}
              </p>
              <div className="mt-4 pt-4 border-t border-slate-800/60 space-y-1.5 text-xs text-slate-300">
                <div className="flex justify-between">
                  <span className="text-slate-500">Tournament ID:</span>
                  <span className="font-mono text-slate-400">{t.tournament_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Current Round:</span>
                  <span>{t.round_name}</span>
                </div>
                {t.champion_username && (
                  <div className="flex justify-between text-amber-400 font-semibold">
                    <span>👑 Champion:</span>
                    <span>@{t.champion_username}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-6 flex gap-2">
              <button
                onClick={() => viewParticipants(t)}
                className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded text-xs font-medium transition"
              >
                Participants
              </button>
              <button
                onClick={() => handleDelete(t.tournament_id)}
                className="p-1.5 bg-red-950/20 text-red-400 hover:bg-red-950/40 border border-red-900/30 rounded transition"
                title="Archive"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Participants Modal */}
      {selectedTournament && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white font-heading uppercase mb-4">
              Registered Participants ({participants.length})
            </h3>
            <div className="max-h-60 overflow-y-auto space-y-2 text-sm text-slate-300">
              {participants.length === 0 ? (
                <p className="text-slate-500 text-xs">No registered players yet.</p>
              ) : (
                participants.map((p, i) => (
                  <div key={i} className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
                    <span>@{p.username}</span>
                    <span className="text-xs text-slate-500 font-mono">{p.user_id}</span>
                  </div>
                ))
              )}
            </div>
            <button
              onClick={() => setSelectedTournament(null)}
              className="mt-6 w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider transition"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white font-heading uppercase mb-4">
              Create New Tournament
            </h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Tournament Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="e.g. Asia Hand Cricket Cup"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  placeholder="Official tournament details..."
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Tournament Mode
                </label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as any)}
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="solo">Solo (100% Automated + 120s Countdown)</option>
                  <option value="host">Host-Managed (Manual Host Control)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Telegram Group ID
                </label>
                <input
                  type="text"
                  value={groupId}
                  onChange={(e) => setGroupId(e.target.value)}
                  required
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
