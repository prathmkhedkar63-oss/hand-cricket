import time
import uuid
import logging
from typing import Tuple, Optional, Dict, Any
from game_engine.models import MatchState, InningsState, BallEvent, MatchStatus, DismissalType
from database.json_manager import db

logger = logging.getLogger("game_engine")

class GameEngine:
    """
    Traditional Hand Cricket Engine:
    - Numbers 0 to 6
    - OUT if both numbers match
    - Runs = batsman number if numbers differ
    - 2 Innings alternating
    - Target = 1st innings runs + 1
    - Chasing target achieved -> Chaser wins
    - Batsman out before target in 2nd innings -> 1st batsman wins
    - Match tie detection
    """

    @staticmethod
    def create_match(
        match_id: str,
        player1_id: int,
        player1_username: str,
        player2_id: int,
        player2_username: str,
        tournament_id: Optional[str] = None,
        round_name: str = "Round 1",
        group_chat_id: Optional[int] = None,
        max_balls: int = 36,
        wickets_per_innings: int = 1,
        mode: str = "host",
        min_number: int = 0,
        max_number: int = 6
    ) -> MatchState:
        now = time.time()
        first_innings = InningsState(
            innings_id=f"{match_id}_inn_1",
            innings_num=1,
            batsman_id=player1_id,
            batsman_username=player1_username,
            bowler_id=player2_id,
            bowler_username=player2_username,
            runs=0,
            wickets=0,
            balls=0,
            is_completed=False
        )

        return MatchState(
            match_id=match_id,
            tournament_id=tournament_id,
            round_name=round_name,
            player1_id=player1_id,
            player1_username=player1_username,
            player2_id=player2_id,
            player2_username=player2_username,
            status=MatchStatus.IN_PROGRESS,
            current_innings=1,
            current_batsman_id=player1_id,
            current_batsman_username=player1_username,
            current_bowler_id=player2_id,
            current_bowler_username=player2_username,
            pending_bowler_number=None,
            pending_bowler_ball_id=None,
            first_innings=first_innings,
            second_innings=None,
            target=None,
            mode=mode,
            min_number=min_number,
            max_number=max_number,
            max_balls=max_balls,
            wickets_per_innings=wickets_per_innings,
            group_chat_id=group_chat_id,
            created_at=now,
            updated_at=now
        )

    @staticmethod
    def record_bowler_choice(match: MatchState, bowler_id: int, number: int) -> Tuple[bool, str]:
        """
        Validates and records bowler choice from private chat.
        """
        if match.status != MatchStatus.IN_PROGRESS:
            return False, f"Match is currently {match.status.value}. No moves allowed."

        if bowler_id != match.current_bowler_id:
            return False, "You are not the designated bowler for this ball."

        if number not in range(match.min_number, match.max_number + 1):
            return False, f"Invalid bowling delivery! Must be between {match.min_number} and {match.max_number}."

        match.pending_bowler_number = number
        match.pending_bowler_ball_id = f"{match.match_id}_b{uuid.uuid4().hex[:6]}"
        match.updated_at = time.time()
        return True, "Your bowling choice has been securely locked in!"

    @staticmethod
    def record_batsman_choice(match: MatchState, batsman_id: int, number: int) -> Tuple[bool, str, Optional[BallEvent]]:
        """
        Validates batsman choice from group, resolves the ball against pending bowler choice.
        Returns: (success, message, ball_event)
        """
        if match.status != MatchStatus.IN_PROGRESS:
            return False, f"Match is {match.status.value}.", None

        if batsman_id != match.current_batsman_id:
            return False, "You are not the active batsman on strike.", None

        if match.pending_bowler_number is None:
            return False, "The bowler has not bowled yet! Please wait for the bowler to deliver.", None

        if number not in range(match.min_number, match.max_number + 1):
            return False, f"Invalid batting shot! Must be between {match.min_number} and {match.max_number}.", None

        now = time.time()
        bowler_num = match.pending_bowler_number
        ball_id = match.pending_bowler_ball_id or f"{match.match_id}_b{uuid.uuid4().hex[:6]}"

        current_inn = match.second_innings if match.current_innings == 2 else match.first_innings
        if not current_inn:
            return False, "Innings not initialized.", None

        current_inn.balls += 1
        is_wicket = (number == bowler_num)
        runs_scored = 0

        if is_wicket:
            current_inn.wickets += 1
            current_inn.recent_balls.append("W")
            dismissal_type = DismissalType.BOWLED
        else:
            runs_scored = number
            current_inn.runs += runs_scored
            current_inn.recent_balls.append(str(runs_scored))
            if runs_scored == 4:
                current_inn.fours += 1
            elif runs_scored == 6:
                current_inn.sixes += 1
            dismissal_type = None

        ball_event = BallEvent(
            ball_id=ball_id,
            match_id=match.match_id,
            tournament_id=match.tournament_id,
            innings_num=match.current_innings,
            ball_number=current_inn.balls,
            batsman_id=match.current_batsman_id,
            batsman_username=match.current_batsman_username,
            bowler_id=match.current_bowler_id,
            bowler_username=match.current_bowler_username,
            bowler_number=bowler_num,
            batsman_number=number,
            runs_scored=runs_scored,
            is_wicket=is_wicket,
            dismissal_type=dismissal_type,
            current_score=current_inn.runs,
            target=match.target,
            timestamp=now
        )

        # Clear pending bowler selection for the next delivery
        match.pending_bowler_number = None
        match.pending_bowler_ball_id = None
        match.updated_at = now

        # Check match / innings transitions
        GameEngine._evaluate_match_state(match, current_inn, is_wicket)

        return True, "Ball completed successfully.", ball_event

    @staticmethod
    def _evaluate_match_state(match: MatchState, current_inn: InningsState, is_wicket: bool):
        """
        Evaluates innings switches, target chases, and match conclusion.
        """
        # First Innings evaluation
        if match.current_innings == 1:
            inn_ended = False
            reason = None

            if current_inn.wickets >= match.wickets_per_innings:
                inn_ended = True
                reason = "All Out"
            elif match.max_balls > 0 and current_inn.balls >= match.max_balls:
                inn_ended = True
                reason = "Overs Completed"

            if inn_ended:
                current_inn.is_completed = True
                current_inn.dismissal_reason = reason
                match.target = current_inn.runs + 1

                # Prepare Second Innings: players switch roles
                match.current_innings = 2
                match.second_innings = InningsState(
                    innings_id=f"{match.match_id}_inn_2",
                    innings_num=2,
                    batsman_id=match.player2_id,
                    batsman_username=match.player2_username,
                    bowler_id=match.player1_id,
                    bowler_username=match.player1_username,
                    runs=0,
                    wickets=0,
                    balls=0,
                    is_completed=False,
                    target=match.target
                )
                match.current_batsman_id = match.player2_id
                match.current_batsman_username = match.player2_username
                match.current_bowler_id = match.player1_id
                match.current_bowler_username = match.player1_username
                logger.info(f"Match {match.match_id}: 1st innings concluded. Target is {match.target}")

        # Second Innings evaluation
        elif match.current_innings == 2:
            target = match.target
            # Target achieved
            if current_inn.runs >= target:
                current_inn.is_completed = True
                match.status = MatchStatus.COMPLETED
                match.winner_id = match.current_batsman_id
                match.winner_username = match.current_batsman_username
                wickets_left = match.wickets_per_innings - current_inn.wickets
                match.result_text = f"@{match.winner_username} won by {wickets_left} wicket(s)!"
                logger.info(f"Match {match.match_id}: Chased successfully. Winner: @{match.winner_username}")

            # Batsman Out or overs finished
            elif current_inn.wickets >= match.wickets_per_innings or (match.max_balls > 0 and current_inn.balls >= match.max_balls):
                current_inn.is_completed = True
                if current_inn.runs == target - 1:
                    match.status = MatchStatus.TIED
                    match.result_text = "Match Tied! Scores are level."
                else:
                    match.status = MatchStatus.COMPLETED
                    match.winner_id = match.current_bowler_id
                    match.winner_username = match.current_bowler_username
                    runs_diff = (target - 1) - current_inn.runs
                    match.result_text = f"@{match.winner_username} won by {runs_diff} run(s)!"
                logger.info(f"Match {match.match_id}: Innings 2 ended. Result: {match.result_text}")

    @staticmethod
    def apply_turn_timeout_penalty(match: MatchState, role: str) -> Dict[str, Any]:
        """
        Applies a 60-second turn timeout penalty:
        - If role == 'bowler': +6 runs to batsman, +1 warning to bowler.
          After 3 warnings -> bowler dismissed (solo: batsman wins; host: paused for host/captain to appoint new bowler).
        - If role == 'batsman': -6 runs from batsman's score, +1 warning to batsman.
          After 3 warnings -> batsman is auto-OUT (triggers innings switch / match end, or host/captain appoint in team match).
        """
        current_inn = match.second_innings if match.current_innings == 2 else match.first_innings
        if not current_inn or match.status != MatchStatus.IN_PROGRESS:
            return {"applied": False}

        now = time.time()
        match.updated_at = now

        if role == "bowler":
            uid = str(match.current_bowler_id)
            warnings = match.player_warnings.get(uid, 0) + 1
            match.player_warnings[uid] = warnings

            current_inn.runs += 6
            dismissed = warnings >= 3

            # Check if 2nd innings target reached via +6 penalty
            if match.current_innings == 2 and match.target is not None and current_inn.runs >= match.target:
                current_inn.is_completed = True
                match.status = MatchStatus.COMPLETED
                match.winner_id = match.current_batsman_id
                match.winner_username = match.current_batsman_username
                wickets_left = match.wickets_per_innings - current_inn.wickets
                match.result_text = f"@{match.winner_username} won by {wickets_left} wicket(s) (target reached via penalty runs)!"
            elif dismissed:
                if match.mode == "solo":
                    current_inn.is_completed = True
                    match.status = MatchStatus.COMPLETED
                    match.winner_id = match.current_batsman_id
                    match.winner_username = match.current_batsman_username
                    match.result_text = f"@{match.current_bowler_username} dismissed after 3 warnings! @{match.current_batsman_username} wins!"
                else:
                    # Host tournament: pause match so host/captain appoints a new bowler
                    match.status = MatchStatus.PAUSED

            return {
                "applied": True,
                "role": "bowler",
                "offender_id": match.current_bowler_id,
                "offender_username": match.current_bowler_username,
                "warnings": warnings,
                "dismissed": dismissed,
                "runs_delta": 6,
                "score": f"{current_inn.runs}/{current_inn.wickets}",
                "needs_appointment": dismissed and match.mode != "solo" and match.status == MatchStatus.PAUSED
            }

        elif role == "batsman":
            uid = str(match.current_batsman_id)
            warnings = match.player_warnings.get(uid, 0) + 1
            match.player_warnings[uid] = warnings

            current_inn.runs = max(0, current_inn.runs - 6)
            dismissed = warnings >= 3

            if dismissed:
                current_inn.wickets += 1
                match.pending_bowler_number = None
                match.pending_bowler_ball_id = None
                GameEngine._evaluate_match_state(match, current_inn, is_wicket=True)

            return {
                "applied": True,
                "role": "batsman",
                "offender_id": match.current_batsman_id,
                "offender_username": match.current_batsman_username,
                "warnings": warnings,
                "dismissed": dismissed,
                "runs_delta": -6,
                "score": f"{current_inn.runs}/{current_inn.wickets}",
                "needs_appointment": False
            }

        return {"applied": False}

    @staticmethod
    def start_super_over(match: MatchState) -> bool:
        """
        Triggers a 1-over (6-ball) Super Over tie-breaker if the match is tied.
        """
        if match.status != MatchStatus.TIED or match.is_super_over:
            return False

        now = time.time()
        # Swap order: 2nd innings chaser bats first in Super Over
        p1_id, p1_user = match.player2_id, match.player2_username
        p2_id, p2_user = match.player1_id, match.player1_username

        match.player1_id = p1_id
        match.player1_username = p1_user
        match.player2_id = p2_id
        match.player2_username = p2_user

        match.is_super_over = True
        match.status = MatchStatus.IN_PROGRESS
        match.current_innings = 1
        match.max_balls = 6
        match.wickets_per_innings = 1
        match.target = None
        match.winner_id = None
        match.winner_username = None
        match.result_text = None
        match.pending_bowler_number = None
        match.pending_bowler_ball_id = None
        match.player_warnings = {}
        if "(Super Over)" not in match.round_name:
            match.round_name = f"{match.round_name} (Super Over)"

        match.first_innings = InningsState(
            innings_id=f"{match.match_id}_so_inn_1",
            innings_num=1,
            batsman_id=p1_id,
            batsman_username=p1_user,
            bowler_id=p2_id,
            bowler_username=p2_user,
            runs=0,
            wickets=0,
            balls=0,
            is_completed=False
        )
        match.second_innings = None
        match.current_batsman_id = p1_id
        match.current_batsman_username = p1_user
        match.current_bowler_id = p2_id
        match.current_bowler_username = p2_user
        match.updated_at = now
        return True
