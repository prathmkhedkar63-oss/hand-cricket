import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { AuditLog } from '../types';
import { FileText } from 'lucide-react';

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    try {
      const res = await api.getAuditLogs();
      setLogs(res || []);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h3 className="text-lg font-bold text-white font-heading uppercase">
          Security & Audit Logs
        </h3>
        <p className="text-xs text-slate-400">
          Permanent chronological log of admin decisions, host actions, player bans, and match overrides
        </p>
      </div>

      <div className="bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-[#0a0d14] text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800 font-heading">
            <tr>
              <th className="px-6 py-3.5">Timestamp</th>
              <th className="px-6 py-3.5">Actor</th>
              <th className="px-6 py-3.5">Action</th>
              <th className="px-6 py-3.5">Target</th>
              <th className="px-6 py-3.5">Details / Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500 font-sans text-sm">
                  No audit logs recorded yet.
                </td>
              </tr>
            ) : (
              logs.map((log, i) => (
                <tr key={i} className="hover:bg-slate-800/30 transition">
                  <td className="px-6 py-3.5 text-slate-400">
                    {new Date(log.timestamp * 1000).toLocaleString()}
                  </td>
                  <td className="px-6 py-3.5 text-emerald-400 font-semibold">
                    {log.actor || 'system'}
                  </td>
                  <td className="px-6 py-3.5 text-amber-300">
                    {log.action}
                  </td>
                  <td className="px-6 py-3.5 text-slate-300">
                    {log.target}
                  </td>
                  <td className="px-6 py-3.5 text-slate-400 max-w-xs truncate">
                    {log.reason || (typeof log.details === 'object' ? JSON.stringify(log.details) : log.details) || '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
