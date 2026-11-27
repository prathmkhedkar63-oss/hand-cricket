import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Player } from '../types';
import { Search, Ban, RotateCcw, CheckCircle, ShieldAlert } from 'lucide-react';

export const Players: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [search, setSearch] = useState('');
  const [selectedPlayer, setSelectedPlayer] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadPlayers();
  }, [search]);

  const loadPlayers = async () => {
    try {
      setLoading(true);
      const res = await api.getPlayers(search);
      setPlayers(res.players || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleBan = async (id: number) => {
    const reason = prompt('Enter reason for banning player:');
    if (!reason) return;
    try {
      await api.banPlayer(id, reason);
      loadPlayers();
      if (selectedPlayer?.user?.user_id === id) {
        viewPlayerDetails(id);
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleUnban = async (id: number) => {
    try {
      await api.unbanPlayer(id);
      loadPlayers();
      if (selectedPlayer?.user?.user_id === id) {
        viewPlayerDetails(id);
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleResetStats = async (id: number) => {
    if (!confirm('Are you sure you want to completely RESET this player statistics to 0?')) return;
    try {
      await api.resetPlayerStats(id);
      alert('Statistics successfully reset.');
      loadPlayers();
      if (selectedPlayer?.user?.user_id === id) {
        viewPlayerDetails(id);
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  const viewPlayerDetails = async (id: number) => {
    try {
      const details = await api.getPlayerDetails(id);
      setSelectedPlayer(details);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 space-y-6">
      {/* Search Header */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by username or ID..."
            className="w-full bg-[#0f1422] border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Players Table */}
      <div className="bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-[#0a0d14] text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800 font-heading">
              <tr>
                <th className="px-6 py-3.5">Player</th>
                <th className="px-6 py-3.5">Telegram ID</th>
                <th className="px-6 py-3.5">Matches (W/L)</th>
                <th className="px-6 py-3.5">Runs</th>
                <th className="px-6 py-3.5">Win Rate</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {players.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                    {loading ? 'Loading players...' : 'No players found.'}
                  </td>
                </tr>
              ) : (
                players.map((p) => {
                  const s = p.stats || { matches_played: 0, matches_won: 0, matches_lost: 0, total_runs: 0, win_percentage: 0 };
                  return (
                    <tr key={p.user_id} className="hover:bg-slate-800/30 transition">
                      <td className="px-6 py-4 font-medium text-white flex items-center gap-2">
                        <span>🏏</span>
                        @{p.username}
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-slate-400">
                        {p.user_id}
                      </td>
                      <td className="px-6 py-4">
                        {s.matches_played} ({s.matches_won}W / {s.matches_lost}L)
                      </td>
                      <td className="px-6 py-4 font-semibold text-emerald-400">
                        {s.total_runs}
                      </td>
                      <td className="px-6 py-4">
                        {s.win_percentage}%
                      </td>
                      <td className="px-6 py-4">
                        {p.is_banned ? (
                          <span className="px-2.5 py-1 text-xs rounded-full bg-red-950/40 text-red-400 border border-red-900/50">
                            Banned
                          </span>
                        ) : (
                          <span className="px-2.5 py-1 text-xs rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-900/50">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={() => viewPlayerDetails(p.user_id)}
                          className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded transition"
                        >
                          View
                        </button>
                        {p.is_banned ? (
                          <button
                            onClick={() => handleUnban(p.user_id)}
                            className="px-2.5 py-1 text-xs bg-emerald-950/30 text-emerald-400 border border-emerald-900/40 hover:bg-emerald-950/60 rounded transition"
                          >
                            Unban
                          </button>
                        ) : (
                          <button
                            onClick={() => handleBan(p.user_id)}
                            className="px-2.5 py-1 text-xs bg-red-950/30 text-red-400 border border-red-900/40 hover:bg-red-950/60 rounded transition"
                          >
                            Ban
                          </button>
                        )}
                        <button
                          onClick={() => handleResetStats(p.user_id)}
                          className="px-2.5 py-1 text-xs bg-amber-950/30 text-amber-400 border border-amber-900/40 hover:bg-amber-950/60 rounded transition"
                          title="Reset Stats"
                        >
                          Reset
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal / Detailed Viewer */}
      {selectedPlayer && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
            <h3 className="text-lg font-bold text-white font-heading uppercase mb-4">
              Player Profile: @{selectedPlayer.user.username}
            </h3>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Telegram ID:</span>
                <span className="font-mono">{selectedPlayer.user.user_id}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Total Runs:</span>
                <span className="font-semibold text-emerald-400">{selectedPlayer.statistics.total_runs}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Highest Score:</span>
                <span>{selectedPlayer.statistics.highest_score}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Batting Avg / Strike Rate:</span>
                <span>{selectedPlayer.statistics.batting_average} / {selectedPlayer.statistics.strike_rate ?? 0}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Boundaries (4s / 6s):</span>
                <span>{selectedPlayer.statistics.fours ?? 0} / {selectedPlayer.statistics.sixes ?? 0}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Bowling (Wkts / Econ):</span>
                <span>{selectedPlayer.statistics.wickets_taken ?? 0} wkts ({selectedPlayer.statistics.economy_rate ?? 0})</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Current / Max Streak:</span>
                <span>{selectedPlayer.statistics.current_streak} / {selectedPlayer.statistics.highest_streak}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">MOTM / Tournaments Won:</span>
                <span className="text-amber-400 font-semibold">{selectedPlayer.statistics.motm_awards ?? 0} / {selectedPlayer.statistics.tournament_victories}</span>
              </div>
              {selectedPlayer.user.is_banned && (
                <div className="p-3 bg-red-950/40 border border-red-900 rounded-lg text-red-300 text-xs">
                  Reason for ban: {selectedPlayer.user.ban_reason || 'Administrative decision'}
                </div>
              )}
            </div>
            <button
              onClick={() => setSelectedPlayer(null)}
              className="mt-6 w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider transition"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
