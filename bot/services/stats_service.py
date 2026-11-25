import time
import logging
from typing import Dict, Any, List, Optional
from database.json_manager import db
from game_engine.models import MatchState, MatchStatus

logger = logging.getLogger("stats_service")

class StatsService:
    @staticmethod
    async def get_or_create_user(user_id: int, username: Optional[str] = None, first_name: str = "") -> Dict[str, Any]:
        uid_str = str(user_id)
        users = await db.load("users")
        now = time.time()

        if uid_str not in users:
            clean_username = username.lstrip("@") if username else f"player_{user_id}"
            users[uid_str] = {
                "user_id": user_id,
                "username": clean_username,
                "display_name": first_name or clean_username,
                "registered_at": now,
                "is_banned": False,
                "ban_reason": None,
                "private_chat_id": user_id
            }
            await db.save("users", users)
            logger.info(f"Registered new player: {user_id} (@{clean_username})")

            # Initialize empty stats
            stats = await db.load("statistics")
            if uid_str not in stats:
                stats[uid_str] = StatsService._create_empty_stats(user_id, clean_username, now)
                await db.save("statistics", stats)
        else:
            # Update username if it changed
            if username:
                clean_username = username.lstrip("@")
                if users[uid_str].get("username") != clean_username:
                    users[uid_str]["username"] = clean_username
                    await db.save("users", users)

        return users[uid_str]

    @staticmethod
    def _create_empty_stats(user_id: int, username: str, registered_at: float) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "username": username,
            "registered_at": registered_at,
            "matches_played": 0,
            "matches_won": 0,
            "matches_lost": 0,
            "matches_drawn": 0,
            "total_runs": 0,
            "highest_score": 0,
            "total_dismissals": 0,
            "batting_average": 0.0,
            "win_percentage": 0.0,
            "current_streak": 0,
            "highest_streak": 0,
            "tournament_participations": 0,
            "tournament_victories": 0,
            "weekly_wins": 0,
            "monthly_wins": 0,
            "last_active": registered_at
        }

    @staticmethod
    async def update_match_stats(match: MatchState):
        """
        Updates statistics for human players upon match completion (skips AI Bot ID).
        """
        from game_engine.bot_ai import BotPsychologyEngine

        stats = await db.load("statistics")
        now = time.time()

        p1_is_bot = (match.player1_id == BotPsychologyEngine.BOT_USER_ID)
        p2_is_bot = (match.player2_id == BotPsychologyEngine.BOT_USER_ID)
        p1_id = str(match.player1_id)
        p2_id = str(match.player2_id)

        if not p1_is_bot and p1_id not in stats:
            stats[p1_id] = StatsService._create_empty_stats(match.player1_id, match.player1_username, now)
        if not p2_is_bot and p2_id not in stats:
            stats[p2_id] = StatsService._create_empty_stats(match.player2_id, match.player2_username, now)

        p1_stats = stats.get(p1_id) if not p1_is_bot else None
        p2_stats = stats.get(p2_id) if not p2_is_bot else None

        p1_inn = match.first_innings
        p2_inn = match.second_innings

        p1_runs = p1_inn.runs if p1_inn else 0
        p2_runs = p2_inn.runs if p2_inn else 0

        p1_dismissed = 1 if (p1_inn and p1_inn.wickets > 0) else 0
        p2_dismissed = 1 if (p2_inn and p2_inn.wickets > 0) else 0

        # Update Player 1
        if p1_stats:
            p1_stats["matches_played"] += 1
            p1_stats["total_runs"] += p1_runs
            p1_stats["highest_score"] = max(p1_stats["highest_score"], p1_runs)
            p1_stats["total_dismissals"] += p1_dismissed
            p1_stats["last_active"] = now

        # Update Player 2
        if p2_stats:
            p2_stats["matches_played"] += 1
            p2_stats["total_runs"] += p2_runs
            p2_stats["highest_score"] = max(p2_stats["highest_score"], p2_runs)
            p2_stats["total_dismissals"] += p2_dismissed
            p2_stats["last_active"] = now

        # Winner / Loser / Tie
        if match.status == MatchStatus.TIED:
            if p1_stats:
                p1_stats["matches_drawn"] += 1
                p1_stats["current_streak"] = 0
            if p2_stats:
                p2_stats["matches_drawn"] += 1
                p2_stats["current_streak"] = 0
        elif match.winner_id == match.player1_id:
            if p1_stats:
                p1_stats["matches_won"] += 1
                p1_stats["weekly_wins"] += 1
                p1_stats["monthly_wins"] += 1
                p1_stats["current_streak"] += 1
                p1_stats["highest_streak"] = max(p1_stats["highest_streak"], p1_stats["current_streak"])
            if p2_stats:
                p2_stats["matches_lost"] += 1
                p2_stats["current_streak"] = 0
        elif match.winner_id == match.player2_id:
            if p2_stats:
                p2_stats["matches_won"] += 1
                p2_stats["weekly_wins"] += 1
                p2_stats["monthly_wins"] += 1
                p2_stats["current_streak"] += 1
                p2_stats["highest_streak"] = max(p2_stats["highest_streak"], p2_stats["current_streak"])
            if p1_stats:
                p1_stats["matches_lost"] += 1
                p1_stats["current_streak"] = 0

        # Recalculate Averages & Win %
        for s in [x for x in (p1_stats, p2_stats) if x]:
            d = max(1, s["total_dismissals"])
            s["batting_average"] = round(s["total_runs"] / d, 2)
            if s["matches_played"] > 0:
                s["win_percentage"] = round((s["matches_won"] / s["matches_played"]) * 100, 1)

        await db.save("statistics", stats)
        await StatsService.refresh_leaderboards()

    @staticmethod
    async def refresh_leaderboards():
        """
        Refreshes all leaderboard categories and persists them.
        """
        stats_dict = await db.load("statistics")
        all_stats = list(stats_dict.values())

        def clean_entry(s):
            return {
                "user_id": s["user_id"],
                "username": s.get("username", f"player_{s['user_id']}"),
                "matches_played": s.get("matches_played", 0),
                "matches_won": s.get("matches_won", 0),
                "total_runs": s.get("total_runs", 0),
                "highest_score": s.get("highest_score", 0),
                "batting_average": s.get("batting_average", 0.0),
                "win_percentage": s.get("win_percentage", 0.0),
                "longest_streak": s.get("highest_streak", 0)
            }

        # Global wins
        by_wins = sorted(all_stats, key=lambda x: (x.get("matches_won", 0), x.get("total_runs", 0)), reverse=True)
        # Highest runs
        by_runs = sorted(all_stats, key=lambda x: x.get("total_runs", 0), reverse=True)
        # Highest individual score
        by_highest_score = sorted(all_stats, key=lambda x: x.get("highest_score", 0), reverse=True)
        # Best win % (minimum 3 matches)
        eligible_win_pct = [s for s in all_stats if s.get("matches_played", 0) >= 3]
        by_win_pct = sorted(eligible_win_pct, key=lambda x: (x.get("win_percentage", 0), x.get("matches_won", 0)), reverse=True)
        # Longest streak
        by_streak = sorted(all_stats, key=lambda x: x.get("highest_streak", 0), reverse=True)

        leaderboard_data = {
            "global_wins": [clean_entry(s) for s in by_wins[:50]],
            "highest_runs": [clean_entry(s) for s in by_runs[:50]],
            "highest_score": [clean_entry(s) for s in by_highest_score[:50]],
            "best_win_percentage": [clean_entry(s) for s in by_win_pct[:50]],
            "longest_streak": [clean_entry(s) for s in by_streak[:50]],
            "weekly": [clean_entry(s) for s in sorted(all_stats, key=lambda x: x.get("weekly_wins", 0), reverse=True)[:50]],
            "monthly": [clean_entry(s) for s in sorted(all_stats, key=lambda x: x.get("monthly_wins", 0), reverse=True)[:50]],
            "last_updated": time.time()
        }

        await db.save("leaderboard", leaderboard_data)
        return leaderboard_data
