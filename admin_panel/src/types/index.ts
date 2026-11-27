export interface Player {
  user_id: number;
  username: string;
  display_name: string;
  registered_at: number;
  is_banned: boolean;
  ban_reason?: string;
  stats?: PlayerStats;
}

export interface PlayerStats {
  matches_played: number;
  matches_won: number;
  matches_lost: number;
  matches_drawn: number;
  total_runs: number;
  highest_score: number;
  batting_average: number;
  balls_faced?: number;
  fours?: number;
  sixes?: number;
  fifties?: number;
  hundreds?: number;
  strike_rate?: number;
  wickets_taken?: number;
  balls_bowled?: number;
  runs_conceded?: number;
  economy_rate?: number;
  motm_awards?: number;
  badges?: string[];
  win_percentage: number;
  current_streak: number;
  highest_streak: number;
  tournament_victories: number;
}

export interface Tournament {
  tournament_id: string;
  name: string;
  description: string;
  mode: 'solo' | 'host';
  status: 'registration' | 'countdown' | 'active' | 'completed' | 'cancelled' | 'archived';
  group_chat_id: number;
  host_id?: number;
  current_round: number;
  round_name: string;
  champion_username?: string;
  created_at: number;
}

export interface Match {
  match_id: string;
  tournament_id?: string;
  round_name: string;
  player1_id: number;
  player1_username: string;
  player2_id: number;
  player2_username: string;
  status: string;
  current_innings: number;
  target?: number;
  winner_id?: number;
  winner_username?: string;
  result_text?: string;
  first_innings?: {
    runs: number;
    wickets: number;
    balls: number;
  };
  second_innings?: {
    runs: number;
    wickets: number;
    balls: number;
  };
  created_at: number;
}

export interface BallHistory {
  ball_id: string;
  match_id: string;
  innings_num: number;
  ball_number: number;
  batsman_username: string;
  bowler_username: string;
  bowler_number: number;
  batsman_number: number;
  runs_scored: number;
  is_wicket: boolean;
  timestamp: number;
}

export interface Host {
  user_id: number;
  username: string;
  assigned_tournaments: string[];
  is_active: boolean;
  assigned_at: number;
}

export interface SystemOverview {
  total_players: number;
  active_players: number;
  total_matches: number;
  ongoing_matches: number;
  completed_matches: number;
  total_tournaments: number;
  active_tournaments: number;
  total_hosts: number;
  daily_activity: number;
  monthly_activity: number;
  storage_mode?: 'postgresql' | 'json';
  storage_label?: string;
  bot_mode?: 'webhook' | 'polling';
}

export interface AuditLog {
  actor: string;
  action: string;
  target: string;
  details?: any;
  reason?: string;
  timestamp: number;
}
