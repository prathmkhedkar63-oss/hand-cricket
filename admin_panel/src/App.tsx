import React, { useState } from 'react';
import { api } from './services/api';
import { Login } from './pages/Login';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Overview } from './pages/Overview';
import { Players } from './pages/Players';
import { Tournaments } from './pages/Tournaments';
import { Hosts } from './pages/Hosts';
import { Matches } from './pages/Matches';
import { Settings } from './pages/Settings';
import { AuditLogs } from './pages/AuditLogs';

export const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(api.getToken());
  const [currentTab, setCurrentTab] = useState('overview');

  const handleLogout = () => {
    api.clearToken();
    setToken(null);
  };

  if (!token) {
    return <Login onSuccess={() => setToken(api.getToken())} />;
  }

  const renderContent = () => {
    switch (currentTab) {
      case 'overview':
        return <Overview />;
      case 'players':
        return <Players />;
      case 'tournaments':
        return <Tournaments />;
      case 'hosts':
        return <Hosts />;
      case 'matches':
        return <Matches />;
      case 'settings':
        return <Settings />;
      case 'audit':
        return <AuditLogs />;
      default:
        return <Overview />;
    }
  };

  return (
    <div className="flex min-h-screen bg-[#07090e] text-slate-100">
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onLogout={handleLogout}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          title={currentTab.replace('-', ' ')}
          onRefresh={() => window.location.reload()}
        />
        <main className="flex-1 overflow-y-auto">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
