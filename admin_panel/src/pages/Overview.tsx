import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { SystemOverview } from '../types';
import { Users, Swords, Trophy, ShieldAlert, Activity, CheckCircle, Flame, Send } from 'lucide-react';

export const Overview: React.FC = () => {
  const [data, setData] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [broadcastText, setBroadcastText] = useState('');
  const [broadcastTarget, setBroadcastTarget] = useState<'all' | 'groups' | 'dms'>('all');
  const [sending, setSending] = useState(false);
  const [broadcastStatus, setBroadcastStatus] = useState('');

  useEffect(() => {
    loadOverview();
  }, []);

  const loadOverview = async () => {
    try {
      setLoading(true);
      const res = await api.getOverview();
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!broadcastText.trim()) return;
    try {
      setSending(true);
      setBroadcastStatus('Sending...');
      const res = await api.broadcast({ message: broadcastText.trim(), target: broadcastTarget });
      setBroadcastText('');
      setBroadcastStatus(`Sent to ${res.dm_sent} DMs & ${res.group_sent} groups (${res.failed} failed).`);
      setTimeout(() => setBroadcastStatus(''), 5000);
    } catch (err: any) {
      setBroadcastStatus(`Error: ${err.message}`);
    } finally {
      setSending(false);
    }
  };

  if (loading || !data) {
    return <div className="p-8 text-slate-400">Loading system metrics...</div>;
  }

  const cards = [
    { label: 'Total Players', value: data.total_players, icon: Users, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { label: 'Active Players', value: data.active_players, icon: Activity, color: 'text-teal-400', bg: 'bg-teal-500/10' },
    { label: 'Live Matches', value: data.ongoing_matches, icon: Flame, color: 'text-amber-400', bg: 'bg-amber-500/10' },
    { label: 'Completed Matches', value: data.completed_matches, icon: CheckCircle, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'Total Tournaments', value: data.total_tournaments, icon: Trophy, color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { label: 'Active Tournaments', value: data.active_tournaments, icon: Swords, color: 'text-rose-400', bg: 'bg-rose-500/10' },
    { label: 'Authorized Hosts', value: data.total_hosts, icon: ShieldAlert, color: 'text-sky-400', bg: 'bg-sky-500/10' },
    { label: 'Monthly Matches', value: data.monthly_activity, icon: Activity, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
  ];

  return (
    <div className="p-8 space-y-8">
      {/* Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {cards.map((c, i) => {
          const Icon = c.icon;
          return (
            <div
              key={i}
              className="bg-[#0f1422] border border-slate-800/80 rounded-xl p-5 shadow-lg relative overflow-hidden group hover:border-slate-700 transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    {c.label}
                  </p>
                  <p className="text-2xl font-bold text-white mt-1.5 font-heading">
                    {c.value}
                  </p>
                </div>
                <div className={`p-3 rounded-lg ${c.bg}`}>
                  <Icon className={`w-5 h-5 ${c.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Esports Arena Status Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#0f1422] border border-slate-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-base font-bold text-white font-heading uppercase tracking-wider mb-4 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Real-Time Engine Status
          </h3>
          <div className="space-y-4 text-sm text-slate-300">
            <div className="flex justify-between items-center py-2.5 border-b border-slate-800/60">
              <span className="text-slate-400">Database Engine</span>
              <span className="text-emerald-400 font-semibold font-mono">
                {data.storage_label || 'Atomic JSON (15 Files Synced)'}
              </span>
            </div>
            <div className="flex justify-between items-center py-2.5 border-b border-slate-800/60">
              <span className="text-slate-400">Telegram Transport</span>
              <span className="text-emerald-400 font-semibold font-mono uppercase">
                {data.bot_mode === 'webhook' ? 'Render HTTPS Webhook (Zero Conflict)' : 'Long Polling'}
              </span>
            </div>
            <div className="flex justify-between items-center py-2.5 border-b border-slate-800/60">
              <span className="text-slate-400">Gameplay Delivery Channel</span>
              <span className="text-emerald-400 font-semibold font-mono">Dual-Channel (DM Bowling + Group Batting)</span>
            </div>
            <div className="flex justify-between items-center py-2.5 border-b border-slate-800/60">
              <span className="text-slate-400">Solo Tournament Engine</span>
              <span className="text-emerald-400 font-semibold font-mono">120s Automated Countdown Active</span>
            </div>
            <div className="flex justify-between items-center py-2.5">
              <span className="text-slate-400">Host Management Controller</span>
              <span className="text-emerald-400 font-semibold font-mono">Role-Based Tournament Isolation Active</span>
            </div>
          </div>
        </div>

        <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-6 shadow-lg flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-white font-heading uppercase tracking-wider mb-3">
              Quick Broadcast
            </h3>
            <form onSubmit={handleBroadcast} className="space-y-2.5">
              <select
                value={broadcastTarget}
                onChange={(e) => setBroadcastTarget(e.target.value as 'all' | 'groups' | 'dms')}
                className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Chats (DMs + Groups)</option>
                <option value="groups">Groups Only</option>
                <option value="dms">Direct Messages Only</option>
              </select>
              <textarea
                rows={3}
                value={broadcastText}
                onChange={(e) => setBroadcastText(e.target.value)}
                placeholder="Type announcement to push to Telegram..."
                className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 resize-none"
              />
              <button
                type="submit"
                disabled={sending || !broadcastText.trim()}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 transition"
              >
                <Send className="w-3.5 h-3.5" />
                {sending ? 'Broadcasting...' : 'Push Announcement'}
              </button>
              {broadcastStatus && (
                <p className="text-[11px] text-emerald-400">{broadcastStatus}</p>
              )}
            </form>
          </div>
          <div className="space-y-2 mt-4 pt-3 border-t border-slate-800/80">
            <button
              onClick={loadOverview}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider transition"
            >
              Sync Telemetry
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
