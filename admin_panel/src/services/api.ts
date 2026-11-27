const API_BASE = '/api';

export const api = {
  getToken: () => localStorage.getItem('hc_token'),
  setToken: (token: string) => localStorage.setItem('hc_token', token),
  clearToken: () => localStorage.removeItem('hc_token'),

  async request(endpoint: string, options: RequestInit = {}) {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      this.clearToken();
      window.location.reload();
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(err.detail || 'Request failed');
    }

    return res.json();
  },

  // Auth
  login: (credentials: any) => api.request('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),

  // Overview
  getOverview: () => api.request('/overview'),

  // Players
  getPlayers: (search = '', page = 1) => api.request(`/players?search=${encodeURIComponent(search)}&page=${page}`),
  getPlayerDetails: (id: number) => api.request(`/players/${id}`),
  banPlayer: (id: number, reason: string) => api.request(`/players/${id}/ban`, { method: 'POST', body: JSON.stringify({ reason }) }),
  unbanPlayer: (id: number) => api.request(`/players/${id}/unban`, { method: 'POST' }),
  resetPlayerStats: (id: number) => api.request(`/players/${id}/reset-stats`, { method: 'POST' }),

  // Tournaments
  getTournaments: () => api.request('/tournaments'),
  createTournament: (data: any) => api.request('/tournaments', { method: 'POST', body: JSON.stringify(data) }),
  deleteTournament: (id: string) => api.request(`/tournaments/${id}`, { method: 'DELETE' }),
  getTournamentParticipants: (id: string) => api.request(`/tournaments/${id}/participants`),
  getTournamentTeams: (id: string) => api.request(`/tournaments/${id}/teams`),
  manageTournamentTeam: (id: string, data: any) => api.request(`/tournaments/${id}/teams`, { method: 'POST', body: JSON.stringify(data) }),

  // Matches
  getMatches: () => api.request('/matches'),
  getMatchDetail: (id: string) => api.request(`/matches/${id}`),
  cancelMatch: (id: string) => api.request(`/matches/${id}/cancel`, { method: 'POST' }),
  overrideMatch: (id: string, data: any) => api.request(`/matches/${id}/override`, { method: 'POST', body: JSON.stringify(data) }),

  // Hosts
  getHosts: () => api.request('/hosts'),
  assignHost: (data: any) => api.request('/hosts', { method: 'POST', body: JSON.stringify(data) }),
  revokeHost: (id: number) => api.request(`/hosts/${id}`, { method: 'DELETE' }),

  // Settings & Audit
  getSettings: () => api.request('/settings'),
  updateSettings: (data: any) => api.request('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getAuditLogs: () => api.request('/audit-logs'),
  createBackup: () => api.request('/system/backup', { method: 'POST' }),
  broadcast: (data: { message: string; target: 'all' | 'groups' | 'dms' }) =>
    api.request('/broadcast', { method: 'POST', body: JSON.stringify(data) }),
  async downloadBackup() {
    const token = this.getToken();
    const res = await fetch(`${API_BASE}/system/backup/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (res.status === 401) {
      this.clearToken();
      window.location.reload();
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      throw new Error('Failed to download backup');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jplbot_backup_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
