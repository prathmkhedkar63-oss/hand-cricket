import asyncio
import random
import time
import logging
from typing import Optional, Dict, Any, Tuple, List
from aiogram import Bot
from aiogram.types import Message, ReactionTypeEmoji
from config.settings import settings
from database.json_manager import db
from game_engine.models import MatchState, MatchStatus
from game_engine.engine import GameEngine
from game_engine.scoreboard import ScoreboardFormatter
from game_engine.bot_ai import BotPsychologyEngine
from bot.keyboards.game_keyboards import get_go_to_dm_keyboard
from bot.services.stats_service import StatsService
from bot.services.media_service import MediaService

logger = logging.getLogger("game_service")

class GameService:
    # In-memory active matches cache for fast live gameplay: match_id -> MatchState
    active_matches: Dict[str, MatchState] = {}
    # Active 60-second turn timers: match_id -> asyncio.Task
    _turn_timers: Dict[str, asyncio.Task] = {}
    # Recent runs per innings for streak/achievement commentary
    _recent_innings_runs: Dict[str, list] = {}
    # Buffered balls flushed to disk at over end / innings break / match end (#11 zero-lag batching)
    _pending_balls: list = []
    # Psychological history buffers for 1v1 Bot matches
    _bot_human_bat_history: Dict[str, List[int]] = {}
    _bot_human_bowl_history: Dict[str, List[int]] = {}
    _bot_last_shot: Dict[str, int] = {}
    TURN_TIMEOUT_SECONDS: int = 60
    POSITIVE_REACTIONS: List[str] = ["🔥", "⚡", "👏", "👍", "🎉", "💯", "🤩"]

    @classmethod
    async def react_positive(cls, message: Message):
        """Reacts to a player's valid delivery or shot with a random positive emoji."""
        emoji = random.choice(cls.POSITIVE_REACTIONS)
        try:
            await message.react([ReactionTypeEmoji(emoji=emoji)])
        except Exception:
            pass

    @classmethod
    async def flush_pending_balls(cls):
        """Flushes buffered ball events to ball_history.json in a single atomic write."""
        if not cls._pending_balls:
            return
        batch = list(cls._pending_balls)
        cls._pending_balls.clear()
        history = await db.load("ball_history")
        history.extend(batch)
        await db.save("ball_history", history)

    @classmethod
    def cancel_turn_timer(cls, match_id: str):
        task = cls._turn_timers.pop(match_id, None)
        if task and not task.done():
            task.cancel()

    @classmethod
    def cleanup_match_cache(cls, match_id: str):
        """Frees in-memory caches for a finished or cancelled match."""
        cls.active_matches.pop(match_id, None)
        cls.cancel_turn_timer(match_id)
        cls._recent_innings_runs.pop(f"{match_id}_1", None)
        cls._recent_innings_runs.pop(f"{match_id}_2", None)
        cls._bot_human_bat_history.pop(match_id, None)
        cls._bot_human_bowl_history.pop(match_id, None)
        cls._bot_last_shot.pop(match_id, None)

    @classmethod
    async def cleanup_match_db(cls, match_id: str):
        """Auto-deletes ball_history records for a completed match so DB stays lean."""
        cls._pending_balls = [b for b in cls._pending_balls if b.get("match_id") != match_id]
        history = await db.load("ball_history")
        if isinstance(history, list):
            cleaned = [b for b in history if not (isinstance(b, dict) and b.get("match_id") == match_id)]
            if len(cleaned) != len(history):
                await db.save("ball_history", cleaned)
        elif isinstance(history, dict):
            keys_to_del = [k for k, v in history.items() if isinstance(v, dict) and v.get("match_id") == match_id]
            if keys_to_del:
                for k in keys_to_del:
                    history.pop(k, None)
                await db.save("ball_history", history)

    @classmethod
    def start_turn_timer(cls, match_id: str, role: str, bot: Bot, timeout_seconds: Optional[int] = None):
        cls.cancel_turn_timer(match_id)
        timeout = timeout_seconds if timeout_seconds is not None else cls.TURN_TIMEOUT_SECONDS
        task = asyncio.create_task(cls._turn_timer_worker(match_id, role, bot, timeout))
        cls._turn_timers[match_id] = task

    @classmethod
    async def _turn_timer_worker(cls, match_id: str, role: str, bot: Bot, timeout_seconds: int):
        try:
            await asyncio.sleep(timeout_seconds)
            match = await cls.get_match(match_id)
            if not match or match.status != MatchStatus.IN_PROGRESS:
                return

            # Ensure we are still waiting on this exact role
            if role == "bowler" and match.pending_bowler_number is not None:
                return
            if role == "batsman" and match.pending_bowler_number is None:
                return

            old_innings = match.current_innings
            res = GameEngine.apply_turn_timeout_penalty(match, role)
            if not res.get("applied"):
                return

            await cls.save_match(match)

            offender = res["offender_username"]
            warnings = res["warnings"]
            delta_str = "+6 runs to batsman" if res["runs_delta"] > 0 else "-6 runs penalty"

            if match.group_chat_id:
                warn_text = (
                    f"⏱️ <b>TURN TIMEOUT (60s)!</b>\n\n"
                    f"⚠️ Warning <b>{warnings}/3</b> for {role.title()} <b>@{offender}</b>!\n"
                    f"📊 Penalty: <b>{delta_str}</b> | Score: <b>{res['score']}</b>\n"
                )
                if res.get("needs_appointment"):
                    warn_text += (
                        f"\n🛑 <b>@{offender} dismissed after 3 warnings!</b>\n"
                        f"Host or Team Captain: use <code>/appoint_bowler @username</code> to appoint a new bowler and resume!"
                    )
                elif res["dismissed"] and role == "batsman":
                    warn_text += f"\n💥 <b>@{offender} is AUTO-OUT after 3 warnings!</b>"

                try:
                    await bot.send_message(chat_id=match.group_chat_id, text=warn_text, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Failed to send timeout warning: {e}")

                await cls._refresh_group_scoreboard(match, bot)

            # Handle match completion
            if match.status in [MatchStatus.COMPLETED, MatchStatus.TIED]:
                cls.active_matches.pop(match.match_id, None)
                cls.cancel_turn_timer(match.match_id)
                await StatsService.update_match_stats(match)
                if match.group_chat_id:
                    try:
                        await bot.send_message(
                            chat_id=match.group_chat_id,
                            text=(
                                f"🏁 <b>MATCH COMPLETED!</b>\n\n"
                                f"🏆 <b>Winner:</b> @{match.winner_username}\n"
                                f"📝 <b>Outcome:</b> {match.result_text}"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                if match.tournament_id:
                    await cls.handle_tournament_match_completion(match, bot)
                return

            # If paused waiting for host/captain appointment, stop here
            if match.status == MatchStatus.PAUSED:
                return

            # Handle innings switch if batsman got auto-out in 1st innings
            if match.current_innings != old_innings and match.group_chat_id:
                break_text = (
                    f"🔔 <b>INNINGS BREAK!</b>\n\n"
                    f"1st Innings Score: <b>{match.first_innings.runs}/{match.first_innings.wickets}</b>\n"
                    f"🎯 <b>TARGET TO WIN: {match.target} runs</b>\n\n"
                    f"🏏 New Batsman: @{match.current_batsman_username}\n"
                    f"🎯 New Bowler: @{match.current_bowler_username}"
                )
                try:
                    await bot.send_message(chat_id=match.group_chat_id, text=break_text, parse_mode="HTML")
                except Exception:
                    pass

            # Continue turn
            if role == "batsman" and not res["dismissed"]:
                # Bowler's pending delivery is still locked; re-prompt batsman & restart batsman timer
                await cls.prompt_batsman_in_group(match, bot)
            else:
                await cls.prompt_bowler(match, bot)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in turn timer worker for {match_id}: {e}")

    @classmethod
    async def _refresh_group_scoreboard(cls, match: MatchState, bot: Bot):
        if not match.group_chat_id:
            return
        sb_text = ScoreboardFormatter.format_live_scoreboard(match)
        if match.group_scoreboard_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=match.group_chat_id,
                    message_id=match.group_scoreboard_msg_id,
                    text=sb_text,
                    parse_mode="HTML"
                )
                return
            except Exception as e:
                if "message is not modified" in str(e).lower():
                    return
        try:
            new_sb = await bot.send_message(chat_id=match.group_chat_id, text=sb_text, parse_mode="HTML")
            match.group_scoreboard_msg_id = new_sb.message_id
            await cls.save_match(match)
        except Exception:
            pass

    @classmethod
    async def get_match(cls, match_id: str) -> Optional[MatchState]:
        if match_id in cls.active_matches:
            return cls.active_matches[match_id]
        
        matches_db = await db.load("matches")
        if match_id in matches_db:
            match_data = matches_db[match_id]
            match = MatchState(**match_data)
            if match.status == MatchStatus.IN_PROGRESS:
                cls.active_matches[match_id] = match
            return match
        return None

    @classmethod
    async def save_match(cls, match: MatchState, flush_disk: bool = True):
        cls.active_matches[match.match_id] = match
        if flush_disk:
            matches_db = await db.load("matches")
            matches_db[match.match_id] = match.model_dump()
            await db.save("matches", matches_db)

    @classmethod
    async def start_new_match(
        cls,
        match_id: str,
        player1_id: int,
        player1_username: str,
        player2_id: int,
        player2_username: str,
        group_chat_id: int,
        bot: Bot,
        tournament_id: Optional[str] = None,
        round_name: str = "Round 1",
        max_balls: int = 36,
        wickets: int = 1,
        mode: str = "host",
        min_number: int = 0,
        max_number: int = 6
    ) -> MatchState:
        match = GameEngine.create_match(
            match_id=match_id,
            player1_id=player1_id,
            player1_username=player1_username,
            player2_id=player2_id,
            player2_username=player2_username,
            tournament_id=tournament_id,
            round_name=round_name,
            group_chat_id=group_chat_id,
            max_balls=max_balls,
            wickets_per_innings=wickets,
            mode=mode,
            min_number=min_number,
            max_number=max_number
        )

        await cls.save_match(match)

        # 1. Send single clean Match Start banner + caption (no separate Ball-0 scorecard spam)
        try:
            p1_clean = match.player1_username.lstrip("@")
            p2_clean = match.player2_username.lstrip("@")
            bat_clean = match.current_batsman_username.lstrip("@")
            bowl_clean = match.current_bowler_username.lstrip("@")
            await MediaService.send_video_or_animation(
                bot=bot,
                chat_id=group_chat_id,
                video_key="on_ready",
                caption=(
                    f"⚔️ <b>JPL CRICKET BOT • MATCH STARTED!</b>\n\n"
                    f"<b>{p1_clean}</b> VS <b>{p2_clean}</b> ({match.round_name})\n"
                    f"🏏 Batting 1st: <b>{bat_clean}</b>\n"
                    f"🎯 Bowling 1st: <b>{bowl_clean}</b>\n\n"
                    f"<i>Use /score anytime to view the live scorecard.</i>"
                )
            )
        except Exception:
            pass

        # 2. Prompt the first bowler (or auto-bowl if Bot is bowling)
        await cls.prompt_bowler(match, bot)

        return match

    @staticmethod
    def _get_bot_username(bot: Bot) -> str:
        me = getattr(bot, "_me", None)
        uname = getattr(me, "username", None) if me else None
        if isinstance(uname, str) and uname:
            return uname
        return settings.BOT_USERNAME

    @classmethod
    async def prompt_bowler(cls, match: MatchState, bot: Bot):
        """
        If Bot is bowling: uses BotPsychologyEngine to choose & deliver immediately.
        If Human is bowling: sends private DM prompt (typed-only) + group 'Go to Bot DM' URL button.
        """
        bowler_id = match.current_bowler_id
        current_inn = match.second_innings if match.current_innings == 2 else match.first_innings

        if bowler_id == BotPsychologyEngine.BOT_USER_ID:
            human_bat_hist = cls._bot_human_bat_history.get(match.match_id, [])
            bot_num = BotPsychologyEngine.choose_bowling_number(
                human_bat_history=human_bat_hist,
                human_runs=current_inn.runs if current_inn else 0,
                balls_played=current_inn.balls if current_inn else 0,
                innings_num=match.current_innings,
                target=match.target,
                max_balls=match.max_balls,
                min_num=match.min_number,
                max_num=match.max_number
            )
            await cls.handle_bowler_delivery(match.match_id, bowler_id, bot_num, bot)
            return

        score_info = f"{current_inn.runs}/{current_inn.wickets} (Ball {current_inn.balls + 1})" if current_inn else "0/0"
        dm_text = (
            f"🎯 <b>YOUR TURN TO BOWL!</b>\n\n"
            f"⚔️ Match: @{match.player1_username} vs @{match.player2_username}\n"
            f"🏏 Batsman: @{match.current_batsman_username}\n"
            f"📊 Innings {match.current_innings} Score: {score_info}\n\n"
            f"Type your bowling number (<b>{match.min_number} to {match.max_number}</b>) here in DM:\n"
            f"⏱️ <i>You have 60 seconds to bowl! (Your choice remains strictly secret)</i>"
        )
        try:
            await bot.send_message(chat_id=bowler_id, text=dm_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not send private message to bowler {bowler_id}: {e}. Bowler must /start the bot.")

        # Send 'Go to Bot DM' URL button in the group for every delivery
        if match.group_chat_id and match.group_chat_id != bowler_id:
            bot_uname = cls._get_bot_username(bot)
            try:
                await bot.send_message(
                    chat_id=match.group_chat_id,
                    text=f"🎯 <b>@{match.current_bowler_username}</b>, your turn to bowl! Tap below to open Bot DM and type <b>{match.min_number}–{match.max_number}</b>:",
                    reply_markup=get_go_to_dm_keyboard(bot_uname),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send Go-to-DM prompt in group: {e}")

        cls.start_turn_timer(match.match_id, "bowler", bot)

    @classmethod
    async def prompt_batsman_in_group(cls, match: MatchState, bot: Bot):
        batsman_id = match.current_batsman_id
        current_inn = match.second_innings if match.current_innings == 2 else match.first_innings

        if batsman_id == BotPsychologyEngine.BOT_USER_ID:
            human_bowl_hist = cls._bot_human_bowl_history.get(match.match_id, [])
            last_bot_shot = cls._bot_last_shot.get(match.match_id)
            bot_num = BotPsychologyEngine.choose_batting_number(
                human_bowl_history=human_bowl_hist,
                bot_runs=current_inn.runs if current_inn else 0,
                balls_played=current_inn.balls if current_inn else 0,
                innings_num=match.current_innings,
                target=match.target,
                max_balls=match.max_balls,
                last_bot_shot=last_bot_shot,
                min_num=match.min_number,
                max_num=match.max_number
            )
            cls._bot_last_shot[match.match_id] = bot_num
            await cls.handle_batsman_shot(match.match_id, batsman_id, bot_num, bot)
            return

        if match.group_chat_id:
            group_prompt = (
                f"🎯 <b>BALL DELIVERED!</b>\n\n"
                f"🏏 <b>@{match.current_batsman_username}</b>, you are on strike!\n"
                f"Type your batting number (<b>{match.min_number} to {match.max_number}</b>) in chat:\n"
                f"⏱️ <i>You have 60 seconds to bat!</i>"
            )
            try:
                await bot.send_message(
                    chat_id=match.group_chat_id,
                    text=group_prompt,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send batting prompt to group: {e}")
        cls.start_turn_timer(match.match_id, "batsman", bot)

    @classmethod
    async def handle_bowler_delivery(cls, match_id: str, bowler_id: int, number: int, bot: Bot) -> Tuple[bool, str]:
        match = await cls.get_match(match_id)
        if not match:
            return False, "Match not found."

        success, msg = GameEngine.record_bowler_choice(match, bowler_id, number)
        if not success:
            return False, msg

        if bowler_id != BotPsychologyEngine.BOT_USER_ID and (
            match.player1_id == BotPsychologyEngine.BOT_USER_ID or match.player2_id == BotPsychologyEngine.BOT_USER_ID
        ):
            cls._bot_human_bowl_history.setdefault(match_id, []).append(number)

        cls.cancel_turn_timer(match_id)
        await cls.save_match(match, flush_disk=False)

        # Notify group/DM that bowler bowled, prompt the batsman & start batsman timer
        await cls.prompt_batsman_in_group(match, bot)

        return True, f"🔒 Bowling choice {number} locked in securely! Waiting for @{match.current_batsman_username} to bat."

    @classmethod
    async def handle_batsman_shot(cls, match_id: str, batsman_id: int, number: int, bot: Bot) -> Tuple[bool, str]:
        match = await cls.get_match(match_id)
        if not match:
            return False, "Match not found."

        old_innings = match.current_innings
        success, msg, ball = GameEngine.record_batsman_choice(match, batsman_id, number)
        if not success:
            return False, msg

        if batsman_id != BotPsychologyEngine.BOT_USER_ID and (
            match.player1_id == BotPsychologyEngine.BOT_USER_ID or match.player2_id == BotPsychologyEngine.BOT_USER_ID
        ):
            cls._bot_human_bat_history.setdefault(match_id, []).append(number)

        cls.cancel_turn_timer(match_id)

        # Buffer ball in memory; flush to disk at over end, innings break, or match completion
        cls._pending_balls.append(ball.model_dump())
        is_over_end = (ball.ball_number > 0 and ball.ball_number % 6 == 0)
        is_innings_break = (match.current_innings != old_innings)
        is_match_end = (match.status in [MatchStatus.COMPLETED, MatchStatus.TIED])
        should_flush = is_over_end or is_innings_break or is_match_end

        if should_flush:
            await cls.flush_pending_balls()
            await cls.save_match(match, flush_disk=True)
        else:
            await cls.save_match(match, flush_disk=False)

        # Track recent runs for achievement commentary (e.g. hat-trick of sixes)
        inn_key = f"{match.match_id}_{ball.innings_num}"
        recent = cls._recent_innings_runs.setdefault(inn_key, [])
        if not ball.is_wicket:
            recent.append(ball.runs_scored)
        else:
            recent.clear()

        # 1. Announce ball result in group (use MP4 clips for out, 50, 100, 6, 4, dot)
        if match.group_chat_id:
            ball_text = ScoreboardFormatter.format_ball_result(ball, match, recent_runs=recent)
            prev_runs = ball.current_score - (0 if ball.is_wicket else ball.runs_scored)
            try:
                if ball.is_wicket:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "out", ball_text)
                elif prev_runs < 100 <= ball.current_score:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "100", ball_text)
                elif prev_runs < 50 <= ball.current_score:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "50", ball_text)
                elif ball.runs_scored == 6:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "6", ball_text)
                elif ball.runs_scored == 4:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "4", ball_text)
                elif ball.runs_scored == 0:
                    await MediaService.send_video_or_animation(bot, match.group_chat_id, "dot", ball_text)
                else:
                    await bot.send_message(chat_id=match.group_chat_id, text=ball_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to announce ball result: {e}")

            # 2. Post Over Scoreboard image at end of over (skip if match just ended)
            is_over_end = (ball.ball_number > 0 and ball.ball_number % 6 == 0)
            is_innings_break = (match.current_innings != old_innings)
            is_match_end = (match.status in [MatchStatus.COMPLETED, MatchStatus.TIED])
            if not is_match_end and (is_over_end or is_innings_break):
                sb_text = ScoreboardFormatter.format_live_scoreboard(match)
                try:
                    if is_over_end and not is_innings_break:
                        from game_engine.scoreboard_image import ScoreboardImageGenerator
                        inn_obj = match.first_innings if ball.innings_num == 1 else match.second_innings
                        if inn_obj:
                            over_bytes = ScoreboardImageGenerator.render_over_card(match, inn_obj)
                            new_sb = await MediaService.send_generated_image(
                                bot, match.group_chat_id, over_bytes, "over_summary.jpg", sb_text
                            )
                        else:
                            new_sb = await bot.send_message(chat_id=match.group_chat_id, text=sb_text, parse_mode="HTML")
                    else:
                        new_sb = await bot.send_message(chat_id=match.group_chat_id, text=sb_text, parse_mode="HTML")
                    if new_sb and isinstance(getattr(new_sb, "message_id", None), int):
                        match.group_scoreboard_msg_id = new_sb.message_id
                        await cls.save_match(match)
                except Exception:
                    pass

        # 3. Auto Super Over on Tie!
        if match.status == MatchStatus.TIED and not match.is_super_over:
            if GameEngine.start_super_over(match):
                await cls.save_match(match)
                if match.group_chat_id:
                    try:
                        await bot.send_message(
                            chat_id=match.group_chat_id,
                            text=(
                                f"🔥 <b>MATCH TIED! SUPER OVER TIME!</b> 🔥\n\n"
                                f"⚔️ 1 Over (6 Balls) per side!\n"
                                f"🏏 Batting 1st: @{match.current_batsman_username}\n"
                                f"🎯 Bowling 1st: @{match.current_bowler_username}\n\n"
                                f"<i>Super Over starting now!</i>"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                await cls.prompt_bowler(match, bot)
                return True, "Super Over started!"

        # 4. Check if Match Completed
        if match.status in [MatchStatus.COMPLETED, MatchStatus.TIED]:
            cls.cleanup_match_cache(match.match_id)
            await StatsService.update_match_stats(match)
            await cls.cleanup_match_db(match.match_id)

            summary_text = ScoreboardFormatter.format_match_summary(match)
            if match.group_chat_id:
                try:
                    await MediaService.send_video_or_animation(
                        bot, match.group_chat_id, "match_over", f"🏁 <b>MATCH OVER!</b>"
                    )
                    from game_engine.scoreboard_image import ScoreboardImageGenerator
                    card_bytes = ScoreboardImageGenerator.render_match_card(match)
                    await MediaService.send_generated_image(
                        bot, match.group_chat_id, card_bytes, "match_scorecard.jpg", summary_text
                    )
                except Exception:
                    pass

            # If this is part of a solo tournament, progress tournament automatically!
            if match.tournament_id:
                await cls.handle_tournament_match_completion(match, bot)

            return True, "Match completed!"

        # 4. Check if Innings Break occurred
        if match.current_innings != old_innings:
            break_text = (
                f"🔔 <b>INNINGS BREAK!</b>\n\n"
                f"1st Innings Score: <b>{match.first_innings.runs}/{match.first_innings.wickets}</b>\n"
                f"🎯 <b>TARGET TO WIN: {match.target} runs</b>\n\n"
                f"Switching roles:\n"
                f"🏏 New Batsman: @{match.current_batsman_username}\n"
                f"🎯 New Bowler: @{match.current_bowler_username}\n\n"
                f"<i>Second innings starting now!</i>"
            )
            if match.group_chat_id:
                try:
                    await bot.send_message(chat_id=match.group_chat_id, text=break_text, parse_mode="HTML")
                except Exception:
                    pass

        # 5. Prompt bowler for the next ball
        await cls.prompt_bowler(match, bot)
        return True, "Ball processed."

    @classmethod
    async def handle_tournament_match_completion(cls, match: MatchState, bot: Bot):
        tournaments = await db.load("tournaments")
        t = tournaments.get(match.tournament_id)
        if not t:
            return

        if t["mode"] == "solo":
            fixtures = t.get("round_fixtures", [])
            idx = t.get("current_fixture_index", 0)
            if idx < len(fixtures):
                fixtures[idx]["status"] = "completed"
                fixtures[idx]["winner"] = {
                    "user_id": match.winner_id,
                    "username": match.winner_username
                }
                t.setdefault("round_winners", []).append({
                    "user_id": match.winner_id,
                    "username": match.winner_username
                })

            t["current_fixture_index"] = idx + 1
            await db.save("tournaments", tournaments)

            # Check if more fixtures remain in this round
            if t["current_fixture_index"] < len(fixtures):
                # Start next fixture after short pause
                await asyncio.sleep(3)
                await cls.start_solo_match_fixture(t["tournament_id"], t["current_fixture_index"], bot)
            else:
                # Round completed! Collect round winners + byes
                advancing = list(t.get("round_winners", [])) + list(t.get("round_byes", []))
                if len(advancing) <= 1:
                    # Tournament champion crowned!
                    champ = advancing[0] if advancing else {"user_id": match.winner_id, "username": match.winner_username}
                    t["status"] = "completed"
                    t["completed_at"] = time.time()
                    t["champion_id"] = champ["user_id"]
                    t["champion_username"] = champ["username"]
                    await db.save("tournaments", tournaments)

                    # Update stats for champion
                    stats = await db.load("statistics")
                    uid_str = str(champ["user_id"])
                    if uid_str in stats:
                        stats[uid_str]["tournament_victories"] = stats[uid_str].get("tournament_victories", 0) + 1
                        await db.save("statistics", stats)

                    champ_text = (
                        f"🏆🎉 <b>JPL CRICKET BOT • TOURNAMENT CHAMPION!</b> 🎉🏆\n\n"
                        f"Tournament: <b>{t['name']}</b>\n"
                        f"👑 Champion: <b>{champ['username'].lstrip('@')}</b>\n\n"
                        f"Congratulations on winning the championship!"
                    )
                    try:
                        await MediaService.send_with_image(bot, t["group_chat_id"], "champion", champ_text)
                    except Exception:
                        pass
                else:
                    # Prepare next round
                    t["current_round"] += 1
                    t["round_name"] = f"Round {t['current_round']}"
                    next_fixtures, next_byes = TournamentService.generate_single_elimination_bracket(advancing, shuffle=True)
                    t["round_fixtures"] = next_fixtures
                    t["round_byes"] = next_byes
                    t["round_winners"] = []
                    t["current_fixture_index"] = 0
                    await db.save("tournaments", tournaments)

                    round_announcement = (
                        f"🔥 <b>{t['round_name'].upper()} STARTING!</b>\n\n"
                        f"🏆 <b>{t['name']}</b>\n"
                    )
                    for i, f in enumerate(next_fixtures, 1):
                        round_announcement += f"{i}. @{f['player1']['username']} VS @{f['player2']['username']}\n"
                    if next_byes:
                        b_str = ", ".join([f"@{b['username']}" for b in next_byes])
                        round_announcement += f"🎟️ Byes: {b_str}\n"

                    try:
                        await bot.send_message(chat_id=t["group_chat_id"], text=round_announcement, parse_mode="HTML")
                    except Exception:
                        pass

                    await asyncio.sleep(3)
                    await cls.start_solo_match_fixture(t["tournament_id"], 0, bot)

    @classmethod
    async def start_solo_match_fixture(cls, tournament_id: str, fixture_index: int, bot: Bot):
        tournaments = await db.load("tournaments")
        t = tournaments.get(tournament_id)
        if not t:
            return

        fixtures = t.get("round_fixtures", [])
        if fixture_index >= len(fixtures):
            return

        f = fixtures[fixture_index]
        p1 = f["player1"]
        p2 = f["player2"]
        match_id = f"sm_{t['tournament_id']}_r{t['current_round']}_m{fixture_index + 1}"

        await cls.start_new_match(
            match_id=match_id,
            player1_id=p1["user_id"],
            player1_username=p1["username"],
            player2_id=p2["user_id"],
            player2_username=p2["username"],
            group_chat_id=t["group_chat_id"],
            bot=bot,
            tournament_id=tournament_id,
            round_name=t.get("round_name", f"Round {t['current_round']}"),
            max_balls=t.get("max_balls", 36),
            wickets=1,
            mode="solo",
            min_number=1,
            max_number=6
        )
