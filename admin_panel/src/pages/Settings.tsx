import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Save, Database } from 'lucide-react';

export const Settings: React.FC = () => {
  const [settings, setSettings] = useState<any>({
    innings_limit: 2,
    wickets_limit: 1,
    max_balls: 36,
    solo_countdown_seconds: 120,
    matchmaking_enabled: true,
    dispute_auto_pause: true,
  });
  const [saved, setSaved] = useState(false);
  const [backupMsg, setBackupMsg] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await api.getSettings();
      if (res) setSettings(res);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleBackup = async () => {
    try {
      setBackupMsg('Creating database snapshot...');
      const res = await api.createBackup();
      setBackupMsg(res.message || 'Backup created successfully!');
      setTimeout(() => setBackupMsg(''), 4000);
    } catch (err: any) {
      alert(err.message);
      setBackupMsg('');
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-4xl">
      <div>
        <h3 className="text-lg font-bold text-white font-heading uppercase">
          System Rules & Configuration
        </h3>
        <p className="text-xs text-slate-400">
          Fine-tune traditional hand cricket mechanics and automated countdown parameters
        </p>
      </div>

      <form onSubmit={handleSave} className="bg-[#0f1422] border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Default Max Deliveries (Overs)
            </label>
            <input
              type="number"
              value={settings.max_balls}
              onChange={(e) => setSettings({ ...settings, max_balls: parseInt(e.target.value) })}
              className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">36 balls = 6 overs per innings. Set 0 for unlimited.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Solo Tournament Countdown (Seconds)
            </label>
            <input
              type="number"
              value={settings.solo_countdown_seconds}
              onChange={(e) => setSettings({ ...settings, solo_countdown_seconds: parseInt(e.target.value) })}
              className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">Mandatory 120s timer before automated bracket generation.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Wickets Per Innings
            </label>
            <input
              type="number"
              value={settings.wickets_limit}
              onChange={(e) => setSettings({ ...settings, wickets_limit: parseInt(e.target.value) })}
              className="w-full bg-[#0a0d14] border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">Traditional 1v1 hand cricket uses 1 wicket per innings.</p>
          </div>

          <div className="flex flex-col justify-center space-y-3 pt-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.matchmaking_enabled}
                onChange={(e) => setSettings({ ...settings, matchmaking_enabled: e.target.checked })}
                className="w-4 h-4 accent-emerald-500 rounded bg-[#0a0d14]"
              />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Enable Public Matchmaking
              </span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.dispute_auto_pause}
                onChange={(e) => setSettings({ ...settings, dispute_auto_pause: e.target.checked })}
                className="w-4 h-4 accent-emerald-500 rounded bg-[#0a0d14]"
              />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Auto-Pause Disputed Matches
              </span>
            </label>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-800/80 flex justify-between items-center">
          <button
            type="submit"
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold uppercase tracking-wider font-heading transition"
          >
            <Save className="w-4 h-4" />
            Save Rules
          </button>
          {saved && <span className="text-xs text-emerald-400">Settings saved successfully!</span>}
        </div>
      </form>

      {/* Database Backup Box */}
      <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-6 shadow-lg flex items-center justify-between">
        <div>
          <h4 className="text-sm font-bold text-white font-heading uppercase">
            Create JSON Database Backup
          </h4>
          <p className="text-xs text-slate-400 mt-0.5">
            Atomically archives all 15 JSON tables to the persistent `/data/backups` directory
          </p>
          {backupMsg && <p className="text-xs text-emerald-400 mt-2">{backupMsg}</p>}
        </div>
        <button
          onClick={handleBackup}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold uppercase tracking-wider transition"
        >
          <Database className="w-4 h-4" />
          Create Snapshot
        </button>
      </div>
    </div>
  );
};
