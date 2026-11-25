import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Match, BallHistory } from '../types';
import { Swords, Eye, XCircle, ShieldCheck } from 'lucide-react';

export const Matches: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [balls, setBalls] = useState<BallHistory[]>([]);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideWinnerId, setOverrideWinnerId] = useState('');
  const [overrideWinnerUsername, setOverrideWinnerUsername] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  useEffect(() => {
    loadMatches();
  }, []);

  const loadMatches = async () => {
    try {
      const res = await api.getMatches();
      setMatches(res || []);
    } catch (err) {
      console.error(err);
    }
  };

  const viewBallHistory = async (m: Match) => {
    setSelectedMatch(m);
    try {
      const res = await api.getMatchDetail(m.match_id);
      setBalls(res.ball_history || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCancelMatch = async (matchId: string) => {
    if (!confirm('Are you sure you want to cancel this match?')) return;
    try {
      await api.cancelMatch(matchId);
      loadMatches();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMatch) return;
    try {
      await api.overrideMatch(selectedMatch.match_id, {
        winner_id: parseInt(overrideWinnerId),
        winner_username: overrideWinnerUsername,
        reason: overrideReason,
      });
      setShowOverrideModal(false);
      loadMatches();
      viewBallHistory(selectedMatch);
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h3 className="text-lg font-bold text-white font-heading uppercase">
          Match Telemetry & Oversight
        </h3>
        <p className="text-xs text-slate-400">
          Inspect ongoing hand cricket battles, review secret bowling vs batting choices, and resolve disputes
        </p>
      </div>

      <div className="bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-[#0a0d14] text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800 font-heading">
            <tr>
              <th className="px-6 py-3.5">Match ID</th>
              <th className="px-6 py-3.5">Combatants</th>
              <th className="px-6 py-3.5">Status</th>
              <th className="px-6 py-3.5">1st Innings</th>
              <th className="px-6 py-3.5">2nd Innings</th>
              <th className="px-6 py-3.5">Target</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {matches.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                  No matches recorded.
                </td>
              </tr>
            ) : (
              matches.map((m) => {
                const f = m.first_innings;
                const s = m.second_innings;
                return (
                  <tr key={m.match_id} className="hover:bg-slate-800/30 transition">
                    <td className="px-6 py-4 font-mono text-xs text-slate-400">
                      {m.match_id}
                    </td>
                    <td className="px-6 py-4 font-medium text-white">
                      @{m.player1_username} <span className="text-slate-500 text-xs">vs</span> @{m.player2_username}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-0.5 text-xs rounded-full font-semibold uppercase ${
                        m.status === 'in_progress' ? 'bg-amber-950/40 text-amber-400 border border-amber-900/50' : 'bg-slate-800 text-slate-300'
                      }`}>
                        {m.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">
                      {f ? `${f.runs}/${f.wickets} (${f.balls}b)` : 'Pending'}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">
                      {s ? `${s.runs}/${s.wickets} (${s.balls}b)` : 'Pending'}
                    </td>
                    <td className="px-6 py-4 font-semibold text-emerald-400">
                      {m.target || '-'}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => viewBallHistory(m)}
                        className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-white rounded transition"
                      >
                        Balls
                      </button>
                      {m.status === 'in_progress' && (
                        <button
                          onClick={() => handleCancelMatch(m.match_id)}
                          className="px-2.5 py-1 text-xs bg-red-950/30 text-red-400 border border-red-900/40 hover:bg-red-950/60 rounded transition"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Ball by Ball History Modal */}
      {selectedMatch && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-base font-bold text-white font-heading uppercase">
                  Ball-By-Ball History: @{selectedMatch.player1_username} vs @{selectedMatch.player2_username}
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  {selectedMatch.match_id} | Result: {selectedMatch.result_text || selectedMatch.status}
                </p>
              </div>
              <button
                onClick={() => setShowOverrideModal(true)}
                className="px-3 py-1 bg-amber-950/30 text-amber-400 border border-amber-900/40 hover:bg-amber-950/60 rounded text-xs uppercase tracking-wider font-semibold transition"
              >
                Override Result
              </button>
            </div>

            <div className="max-h-72 overflow-y-auto space-y-2 pr-2 text-xs">
              {balls.length === 0 ? (
                <p className="text-slate-500 py-4 text-center">No deliveries bowled in this match yet.</p>
              ) : (
                balls.map((b, i) => (
                  <div
                    key={i}
                    className={`p-2.5 rounded-lg border flex justify-between items-center ${
                      b.is_wicket
                        ? 'bg-red-950/20 border-red-900/50 text-red-300'
                        : 'bg-[#0a0d14] border-slate-800/80 text-slate-300'
                    }`}
                  >
                    <div>
                      <span className="font-semibold text-white">Ball #{b.ball_number} (Inn {b.innings_num}):</span>
                      <span className="ml-2">Batsman @{b.batsman_username} ({b.batsman_number}) vs Bowler @{b.bowler_username} ({b.bowler_number})</span>
                    </div>
                    <div className="font-semibold">
                      {b.is_wicket ? '💥 OUT' : `+${b.runs_scored} Runs`}
                    </div>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={() => setSelectedMatch(null)}
              className="mt-6 w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider transition"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Override Result Modal */}
      {showOverrideModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1422] border border-amber-900/50 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-base font-bold text-amber-400 font-heading uppercase mb-2">
              Override Match Result
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              All overrides are securely recorded in the permanent audit logs with timestamp and reason.
            </p>
            <form onSubmit={handleOverrideSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Winner Telegram User ID
                </label>
                <input
                  type="number"
                  value={overrideWinnerId}
                  onChange={(e) => setOverrideWinnerId(e.target.value)}
                  required
                  placeholder="Winner Telegram ID"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Winner Username
                </label>
                <input
                  type="text"
                  value={overrideWinnerUsername}
                  onChange={(e) => setOverrideWinnerUsername(e.target.value)}
                  required
                  placeholder="e.g. winner123"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Justification / Reason
                </label>
                <textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  required
                  rows={2}
                  placeholder="e.g. Opponent forfeited after technical glitch"
                  className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOverrideModal(false)}
                  className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold uppercase tracking-wider"
                >
                  Confirm Override
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
