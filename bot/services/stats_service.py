import time
import html
import logging
from typing import Dict, Any, List, Optional
from database.json_manager import db
from game_engine.models import MatchState, MatchStatus

logger = logging.getLogger("stats_service")


def resolve_player_name(user) -> str:
    """Returns @username (stripped) if set, otherwise Telegram full_name/first_name."""
    uname = getattr(user, "username", None)
    if isinstance(uname, str) and uname.lstrip("@").strip():
        return uname.lstrip("@").strip()
    full = getattr(user, "full_name", None)
    if isinstance(full, str) and full.strip():
        return full.strip()
    first = getattr(user, "first_name", None)
    last = getattr(user, "last_name", None)
    parts = [p.strip() for p in (first, last) if isinstance(p, str) and p.strip()]
    if parts:
        return " ".join(parts)
    uid = getattr(user, "id", "")
    return f"Player {uid}".strip()


def format_user_tag(user_id: int, display_name: str) -> str:
    """Clickable Telegram mention tag without noisy @username spam (works without @username too)."""
    clean = html.escape((display_name or f"Player {user_id}").lstrip("@"))
    return f'<a href="tg://user?id={user_id}">{clean}</a>'


class StatsService:
    @staticmethod
    async def get_or_create_user(user_id: int, username: Optional[str] = None, first_name: str = "") -> Dict[str, Any]:
        uid_str = str(user_id)
        users = await db.load("users")
        now = time.time()
        clean_uname = username.lstrip("@").strip() if isinstance(username, str) and username.lstrip("@").strip() else ""
        clean_first = first_name.strip() if isinstance(first_name, str) and first_name.strip() else ""
        preferred_name = clean_uname or clean_first or f"Player {user_id}"

        if uid_str not in users:
            users[uid_str] = {
                "user_id": user_id,
                "username": preferred_name,
                "display_name": clean_first or preferred_name,
                "registered_at": now,
                "is_banned": False,
                "ban_reason": None,
                "private_chat_id": user_id
            }
            await db.save("users", users)
            logger.info(f"Registered new player: {user_id} ({preferred_name})")

            # Initialize empty stats
            stats = await db.load("statistics")
            if uid_str not in stats:
                stats[uid_str] = StatsService._create_empty_stats(user_id, preferred_name, now)
                await db.save("statistics", stats)
        else:
            existing = users[uid_str]
            cur_name = existing.get("username", "")
            needs_upgrade = (
                (clean_uname and cur_name != clean_uname)
                or (not clean_uname and clean_first and (not cur_name or cur_name.startswith("player_") or cur_name.startswith("Player ")))
            )
            if needs_upgrade:
                existing["username"] = preferred_name
                if clean_first:
                    existing["display_name"] = clean_first
                await db.save("users", users)
                stats = await db.load("statistics")
                if uid_str in stats:
                    stats[uid_str]["username"] = preferred_name
                    await db.save("statistics", stats)
            elif clean_first and existing.get("display_name", "").startswith("player_"):
                existing["display_name"] = clean_first
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
        if match.is_solo_rotation:
            await StatsService.update_solo_rotation_stats(match)
            return

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
    async def update_solo_rotation_stats(match: MatchState):
        """Updates career stats for every participant in a multi-player Solo Rotation match."""
        stats = await db.load("statistics")
        now = time.time()
        for uid_str, p in match.solo_player_stats.items():
            uid = int(p["user_id"])
            uname = p.get("username") or f"Player {uid}"
            if uid_str not in stats:
                stats[uid_str] = StatsService._create_empty_stats(uid, uname, now)
            rec = stats[uid_str]
            runs = p.get("runs", 0)
            rec["matches_played"] += 1
            rec["total_runs"] += runs
            rec["highest_score"] = max(rec["highest_score"], runs)
            if p.get("is_out"):
                rec["total_dismissals"] += 1
            rec["last_active"] = now
            if match.winner_id == uid:
                rec["matches_won"] += 1
                rec["weekly_wins"] += 1
                rec["monthly_wins"] += 1
                rec["current_streak"] += 1
                rec["highest_streak"] = max(rec["highest_streak"], rec["current_streak"])
            else:
                rec["matches_lost"] += 1
                rec["current_streak"] = 0
            d = max(1, rec["total_dismissals"])
            rec["batting_average"] = round(rec["total_runs"] / d, 2)
            rec["win_percentage"] = round((rec["matches_won"] / rec["matches_played"]) * 100, 1)
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
