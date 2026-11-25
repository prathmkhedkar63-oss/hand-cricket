import React from 'react';
import { ShieldCheck, RefreshCw } from 'lucide-react';

interface HeaderProps {
  title: string;
  onRefresh?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, onRefresh }) => {
  return (
    <header className="h-16 bg-[#0a0d14]/80 backdrop-blur border-b border-slate-800 px-8 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold text-white font-heading tracking-wide uppercase">
          {title}
        </h2>
      </div>

      <div className="flex items-center gap-4">
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="p-2 text-slate-400 hover:text-white bg-slate-900/60 hover:bg-slate-800 border border-slate-800 rounded-lg transition"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        )}

        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-950/30 border border-emerald-900/40 rounded-full">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">
            SuperAdmin Connected
          </span>
        </div>
      </div>
    </header>
  );
};
