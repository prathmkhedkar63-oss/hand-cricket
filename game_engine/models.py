from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    INNINGS_BREAK = "innings_break"
    COMPLETED = "completed"
    TIED = "tied"
    ABANDONED = "abandoned"
    DISPUTED = "disputed"

class DismissalType(str, Enum):
    BOWLED = "bowled"          # numbers matched
    MAX_BALLS = "max_balls"    # overs completed
    DISQUALIFIED = "disqualified"
    TIME_OUT = "timed_out"

class InningsState(BaseModel):
    innings_id: str
    innings_num: int            # 1 or 2
    batsman_id: int
    batsman_username: str
    bowler_id: int
    bowler_username: str
    runs: int = 0
    wickets: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    recent_balls: List[str] = Field(default_factory=list)
    is_completed: bool = False
    dismissal_reason: Optional[str] = None
    target: Optional[int] = None

class BallEvent(BaseModel):
    ball_id: str
    match_id: str
    tournament_id: Optional[str] = None
    innings_num: int
    ball_number: int
    batsman_id: int
    batsman_username: str
    bowler_id: int
    bowler_username: str
    bowler_number: Optional[int] = None
    batsman_number: Optional[int] = None
    runs_scored: int = 0
    is_wicket: bool = False
    dismissal_type: Optional[DismissalType] = None
    current_score: int = 0
    target: Optional[int] = None
    timestamp: float

class MatchState(BaseModel):
    match_id: str
    tournament_id: Optional[str] = None
    round_name: str = "Round 1"
    player1_id: int
    player1_username: str
    player2_id: int
    player2_username: str
    
    status: MatchStatus = MatchStatus.SCHEDULED
    current_innings: int = 1
    
    # Active players for current ball
    current_batsman_id: int
    current_batsman_username: str
    current_bowler_id: int
    current_bowler_username: str

    # Bowling selection submitted in private chat (kept secret until batsman submits)
    pending_bowler_number: Optional[int] = None
    pending_bowler_ball_id: Optional[str] = None

    # Innings records
    first_innings: Optional[InningsState] = None
    second_innings: Optional[InningsState] = None

    target: Optional[int] = None
    winner_id: Optional[int] = None
    winner_username: Optional[str] = None
    result_text: Optional[str] = None

    # Configs
    mode: str = "host"           # 'solo' or 'host'
    is_super_over: bool = False
    min_number: int = 0          # 1 for solo, 0 for host
    max_number: int = 6
    max_balls: int = 36          # 0 for unlimited
    wickets_per_innings: int = 1 # Traditional 1v1 hand cricket is 1 wicket
    player_warnings: Dict[str, int] = Field(default_factory=dict)
    group_chat_id: Optional[int] = None
    group_scoreboard_msg_id: Optional[int] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    # Solo Tournament Rotation State (multi-player cycle: bat until OUT, bowl 6 balls / mid-over takeover)
    is_solo_rotation: bool = False
    solo_roster: List[Dict[str, Any]] = Field(default_factory=list)
    solo_batsman_idx: int = 0
    solo_bowler_idx: int = 1
    solo_over_balls: int = 0
    solo_completed_overs: int = 0
    solo_over_recent_balls: List[str] = Field(default_factory=list)
    solo_player_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
