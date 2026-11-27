import asyncio
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

    BADGE_LABELS: Dict[str, str] = {
        "first_win": "🥇 First Blood",
        "half_century": "🔥 Half-Centurion (50+)",
        "century": "👑 Centurion (100+)",
        "six_machine": "💥 Six Machine (10+ Sixes)",
        "golden_arm": "🎯 Golden Arm (10+ Wkts)",
        "unstoppable": "⚡ Streak Master (3+ Wins)",
        "motm_star": "🌟 Match MVP (3+ MOTM)",
        "cup_winner": "🏆 Cup Champion",
    }

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
            "balls_faced": 0,
            "fours": 0,
            "sixes": 0,
            "fifties": 0,
            "hundreds": 0,
            "ducks": 0,
            "batting_average": 0.0,
            "strike_rate": 0.0,
            "wickets_taken": 0,
            "balls_bowled": 0,
            "runs_conceded": 0,
            "economy_rate": 0.0,
            "win_percentage": 0.0,
            "current_streak": 0,
            "highest_streak": 0,
            "tournament_participations": 0,
            "tournament_victories": 0,
            "motm_awards": 0,
            "badges": [],
            "weekly_wins": 0,
            "monthly_wins": 0,
            "last_active": registered_at
        }

    @staticmethod
    def _ensure_stats_fields(rec: Dict[str, Any]) -> Dict[str, Any]:
        """Backfills new all-rounder/badge keys on legacy player statistics records."""
        int_defaults = (
            "matches_played", "matches_won", "matches_lost", "matches_drawn",
            "total_runs", "highest_score", "total_dismissals",
            "balls_faced", "fours", "sixes", "fifties", "hundreds", "ducks",
            "wickets_taken", "balls_bowled", "runs_conceded",
            "current_streak", "highest_streak",
            "tournament_participations", "tournament_victories", "motm_awards",
            "weekly_wins", "monthly_wins",
        )
        for k in int_defaults:
            rec.setdefault(k, 0)
        for k in ("batting_average", "strike_rate", "economy_rate", "win_percentage"):
            rec.setdefault(k, 0.0)
        if not isinstance(rec.get("badges"), list):
            rec["badges"] = []
        return rec

    @staticmethod
    def _recalc_career_rates(rec: Dict[str, Any]) -> None:
        d = max(1, rec.get("total_dismissals", 0))
        rec["batting_average"] = round(rec.get("total_runs", 0) / d, 2)
        bf = rec.get("balls_faced", 0)
        rec["strike_rate"] = round((rec.get("total_runs", 0) / bf) * 100, 1) if bf > 0 else 0.0
        bb = rec.get("balls_bowled", 0)
        rec["economy_rate"] = round((rec.get("runs_conceded", 0) / bb) * 6, 2) if bb > 0 else 0.0
        mp = rec.get("matches_played", 0)
        if mp > 0:
            rec["win_percentage"] = round((rec.get("matches_won", 0) / mp) * 100, 1)

    @classmethod
    def evaluate_badges(cls, rec: Dict[str, Any]) -> List[str]:
        """Unlocks career achievement badges idempotently and returns newly unlocked labels."""
        cls._ensure_stats_fields(rec)
        owned = set(rec["badges"])
        checks = [
            ("first_win", rec["matches_won"] >= 1),
            ("half_century", rec["highest_score"] >= 50 or rec["fifties"] >= 1),
            ("century", rec["highest_score"] >= 100 or rec["hundreds"] >= 1),
            ("six_machine", rec["sixes"] >= 10),
            ("golden_arm", rec["wickets_taken"] >= 10),
            ("unstoppable", rec["highest_streak"] >= 3),
            ("motm_star", rec["motm_awards"] >= 3),
            ("cup_winner", rec["tournament_victories"] >= 1),
        ]
        newly_unlocked: List[str] = []
        for key, condition in checks:
            if condition and key not in owned:
                rec["badges"].append(key)
                owned.add(key)
                newly_unlocked.append(cls.BADGE_LABELS[key])
        return newly_unlocked

    @staticmethod
    def compute_man_of_the_match(match: MatchState) -> Optional[Dict[str, Any]]:
        """Computes Man of the Match across human players and records motm_id/motm_username on match."""
        from game_engine.bot_ai import BotPsychologyEngine

        candidates: Dict[int, Dict[str, Any]] = {}
        if match.is_solo_rotation:
            for p in match.solo_player_stats.values():
                uid = int(p["user_id"])
                if uid == BotPsychologyEngine.BOT_USER_ID:
                    continue
                runs = p.get("runs", 0)
                fours = p.get("fours", 0)
                sixes = p.get("sixes", 0)
                wkts = p.get("wickets_taken", 0)
                conceded = p.get("runs_conceded", 0)
                win_bonus = 15.0 if match.winner_id == uid else 0.0
                score = runs + (fours * 1.5) + (sixes * 2.5) + (wkts * 15.0) + win_bonus - (conceded * 0.25)
                candidates[uid] = {
                    "user_id": uid,
                    "username": p.get("username") or f"Player {uid}",
                    "points": score,
                }
        else:
            for pid, puname in (
                (match.player1_id, match.player1_username),
                (match.player2_id, match.player2_username),
            ):
                if pid != BotPsychologyEngine.BOT_USER_ID:
                    candidates[pid] = {
                        "user_id": pid,
                        "username": puname or f"Player {pid}",
                        "points": 20.0 if match.winner_id == pid else 0.0,
                    }
            for inn in (match.first_innings, match.second_innings):
                if not inn:
                    continue
                if inn.batsman_id in candidates:
                    candidates[inn.batsman_id]["points"] += inn.runs + (inn.fours * 1.5) + (inn.sixes * 2.5)
                if inn.bowler_id in candidates:
                    candidates[inn.bowler_id]["points"] += inn.wickets * 15.0

        if not candidates:
            return None

        best = max(
            candidates.values(),
            key=lambda c: (c["points"], 1 if c["user_id"] == match.winner_id else 0)
        )
        match.motm_id = best["user_id"]
        match.motm_username = best["username"]
        return best

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

        p1_stats = StatsService._ensure_stats_fields(stats[p1_id]) if not p1_is_bot else None
        p2_stats = StatsService._ensure_stats_fields(stats[p2_id]) if not p2_is_bot else None

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

        # Accumulate batting boundaries/balls & bowling wickets/overs across both innings
        stats_by_id = {match.player1_id: p1_stats, match.player2_id: p2_stats}
        for inn in (p1_inn, p2_inn):
            if not inn:
                continue
            b_rec = stats_by_id.get(inn.batsman_id)
            if b_rec:
                b_rec["balls_faced"] += inn.balls
                b_rec["fours"] += inn.fours
                b_rec["sixes"] += inn.sixes
                if inn.runs >= 100:
                    b_rec["hundreds"] += 1
                elif inn.runs >= 50:
                    b_rec["fifties"] += 1
                if inn.runs == 0 and inn.wickets > 0:
                    b_rec["ducks"] += 1
            bw_rec = stats_by_id.get(inn.bowler_id)
            if bw_rec:
                bw_rec["wickets_taken"] += inn.wickets
                bw_rec["balls_bowled"] += inn.balls
                bw_rec["runs_conceded"] += inn.runs

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

        motm = StatsService.compute_man_of_the_match(match)
        if motm and stats_by_id.get(motm["user_id"]):
            stats_by_id[motm["user_id"]]["motm_awards"] += 1

        # Recalculate Averages, Strike Rate, Economy, Win %, and evaluate Badges
        for s in [x for x in (p1_stats, p2_stats) if x]:
            StatsService._recalc_career_rates(s)
            StatsService.evaluate_badges(s)

        await db.save("statistics", stats)
        StatsService.schedule_leaderboard_refresh()

    @staticmethod
    async def update_solo_rotation_stats(match: MatchState):
        """Updates all-rounder career stats, MOTM, and badges for every Solo Rotation participant."""
        stats = await db.load("statistics")
        now = time.time()
        for uid_str, p in match.solo_player_stats.items():
            uid = int(p["user_id"])
            uname = p.get("username") or f"Player {uid}"
            if uid_str not in stats:
                stats[uid_str] = StatsService._create_empty_stats(uid, uname, now)
            rec = StatsService._ensure_stats_fields(stats[uid_str])
            runs = p.get("runs", 0)
            balls = p.get("balls", 0)
            rec["matches_played"] += 1
            rec["total_runs"] += runs
            rec["highest_score"] = max(rec["highest_score"], runs)
            rec["balls_faced"] += balls
            rec["fours"] += p.get("fours", 0)
            rec["sixes"] += p.get("sixes", 0)
            rec["wickets_taken"] += p.get("wickets_taken", 0)
            rec["balls_bowled"] += p.get("balls_bowled", 0)
            rec["runs_conceded"] += p.get("runs_conceded", 0)
            if runs >= 100:
                rec["hundreds"] += 1
            elif runs >= 50:
                rec["fifties"] += 1
            if p.get("is_out"):
                rec["total_dismissals"] += 1
                if runs == 0:
                    rec["ducks"] += 1
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

        motm = StatsService.compute_man_of_the_match(match)
        if motm and str(motm["user_id"]) in stats:
            stats[str(motm["user_id"])]["motm_awards"] = stats[str(motm["user_id"])].get("motm_awards", 0) + 1

        for uid_str in match.solo_player_stats:
            if uid_str in stats:
                StatsService._recalc_career_rates(stats[uid_str])
                StatsService.evaluate_badges(stats[uid_str])

        await db.save("statistics", stats)
        StatsService.schedule_leaderboard_refresh()

    _refresh_task: Optional[asyncio.Task] = None
    _refresh_dirty: bool = False

    @classmethod
    def schedule_leaderboard_refresh(cls) -> None:
        """Runs leaderboard recomputation in the background, coalescing rapid bursts."""
        cls._refresh_dirty = True
        if cls._refresh_task and not cls._refresh_task.done():
            return

        async def _runner():
            try:
                while cls._refresh_dirty:
                    cls._refresh_dirty = False
                    await cls.refresh_leaderboards()
            except Exception as e:
                logger.error(f"Background leaderboard refresh error: {e}")

        try:
            asyncio.get_running_loop()
            cls._refresh_task = asyncio.create_task(_runner())
        except RuntimeError:
            pass

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
                "strike_rate": s.get("strike_rate", 0.0),
                "fours": s.get("fours", 0),
                "sixes": s.get("sixes", 0),
                "wickets_taken": s.get("wickets_taken", 0),
                "economy_rate": s.get("economy_rate", 0.0),
                "motm_awards": s.get("motm_awards", 0),
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
        # Most wickets & sixes & MOTM
        by_wickets = sorted(all_stats, key=lambda x: (x.get("wickets_taken", 0), -x.get("runs_conceded", 0)), reverse=True)
        by_sixes = sorted(all_stats, key=lambda x: (x.get("sixes", 0), x.get("total_runs", 0)), reverse=True)
        by_motm = sorted(all_stats, key=lambda x: (x.get("motm_awards", 0), x.get("matches_won", 0)), reverse=True)

        leaderboard_data = {
            "global_wins": [clean_entry(s) for s in by_wins[:50]],
            "highest_runs": [clean_entry(s) for s in by_runs[:50]],
            "highest_score": [clean_entry(s) for s in by_highest_score[:50]],
            "best_win_percentage": [clean_entry(s) for s in by_win_pct[:50]],
            "longest_streak": [clean_entry(s) for s in by_streak[:50]],
            "most_wickets": [clean_entry(s) for s in by_wickets[:50]],
            "most_sixes": [clean_entry(s) for s in by_sixes[:50]],
            "motm": [clean_entry(s) for s in by_motm[:50]],
            "weekly": [clean_entry(s) for s in sorted(all_stats, key=lambda x: x.get("weekly_wins", 0), reverse=True)[:50]],
            "monthly": [clean_entry(s) for s in sorted(all_stats, key=lambda x: x.get("monthly_wins", 0), reverse=True)[:50]],
            "last_updated": time.time()
        }

        await db.save("leaderboard", leaderboard_data)
        return leaderboard_data
