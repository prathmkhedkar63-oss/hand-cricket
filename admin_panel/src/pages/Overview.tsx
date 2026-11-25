import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { SystemOverview } from '../types';
import { Users, Swords, Trophy, ShieldAlert, Activity, CheckCircle, Flame } from 'lucide-react';

export const Overview: React.FC = () => {
  const [data, setData] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);

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
              <span className="text-emerald-400 font-semibold font-mono">Atomic JSON (15 Files Synced)</span>
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
            <h3 className="text-base font-bold text-white font-heading uppercase tracking-wider mb-4">
              Quick Admin Actions
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Create and manage tournaments, monitor live ball deliveries, override dispute matches, and export system backups directly from this console.
            </p>
          </div>
          <div className="space-y-2 mt-6">
            <button
              onClick={loadOverview}
              className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold uppercase tracking-wider transition"
            >
              Sync Telemetry
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
