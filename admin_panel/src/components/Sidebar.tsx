import React from 'react';
import { 
  LayoutDashboard, 
  Users, 
  Trophy, 
  ShieldAlert, 
  Swords, 
  Sliders, 
  FileText,
  LogOut 
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, onLogout }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'players', label: 'Player Management', icon: Users },
    { id: 'tournaments', label: 'Tournaments', icon: Trophy },
    { id: 'hosts', label: 'Host Management', icon: ShieldAlert },
    { id: 'matches', label: 'Live & Past Matches', icon: Swords },
    { id: 'settings', label: 'System Settings', icon: Sliders },
    { id: 'audit', label: 'Audit Logs', icon: FileText },
  ];

  return (
    <aside className="w-64 bg-[#0d111c] border-r border-slate-800 flex flex-col flex-shrink-0 min-h-screen">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <span className="text-xl">🏏</span>
        </div>
        <div>
          <h1 className="text-lg font-bold text-white tracking-wider font-heading leading-tight">
            HAND CRICKET
          </h1>
          <p className="text-[10px] text-emerald-400 font-medium uppercase tracking-widest">
            ESPORTS CONTROL
          </p>
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shadow-inner'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer / Logout */}
      <div className="p-4 border-t border-slate-800">
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-red-400 bg-red-950/20 hover:bg-red-950/40 border border-red-900/30 rounded-lg transition"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  );
};
