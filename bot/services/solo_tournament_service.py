import asyncio
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from database.json_manager import db
from bot.services.tournament_service import TournamentService
from bot.keyboards.game_keyboards import get_tournament_register_keyboard
from config.settings import settings

logger = logging.getLogger("solo_tournament_service")

class SoloTournamentService:
    """
    100% Automated Solo Player Tournament Engine:
    - 120-second countdown with restart recovery
    - Auto-bracket generation with byes
    - Automatic progression from round to round
    - Automatic champion announcement
    """
    _running_countdowns: Dict[str, asyncio.Task] = {}

    @classmethod
    async def start_countdown(cls, tournament_id: str, bot_instance, group_chat_id: int):
        tournaments = await db.load("tournaments")
        t = tournaments.get(tournament_id)
        if not t:
            return False, "Tournament not found."

        if t["mode"] != "solo":
            return False, "This tournament is not a Solo Tournament."

        if t["status"] not in ["registration", "countdown"]:
            return False, f"Tournament is already {t['status']}."

        participants = await TournamentService.get_tournament_participants(tournament_id)

        now = time.time()
        countdown_secs = settings.SOLO_TOURNAMENT_COUNTDOWN_SECONDS # 120 seconds
        end_time = now + countdown_secs

        t["status"] = "countdown"
        t["countdown_end_time"] = end_time
        await db.save("tournaments", tournaments)

        # Cancel any previous task if existing
        if tournament_id in cls._running_countdowns:
            cls._running_countdowns[tournament_id].cancel()

        # Announce start of countdown cleanly (no internal IDs, no @ pings)
        player_lines = "\n".join(
            [f"{i}. <b>{p['username'].lstrip('@')}</b>" for i, p in enumerate(participants, 1)]
        ) or "None yet"
        announcement = (
            f"🏏 <b>JPL CRICKET BOT • SOLO TOURNAMENT</b>\n\n"
            f"🏆 <b>{t['name']}</b>\n"
            f"🔢 Numbers: <b>1 to 6</b> | ⏱️ Turn Timer: <b>60s</b>\n"
            f"👥 Joined Players (<b>{len(participants)}</b>):\n"
            f"{player_lines}\n\n"
            f"⏳ Starts in: <b>02:00</b>"
        )
        try:
            from bot.services.media_service import MediaService
            msg = await MediaService.send_with_image(
                bot=bot_instance,
                chat_id=group_chat_id,
                image_key="match_start",
                caption=announcement,
                reply_markup=get_tournament_register_keyboard(tournament_id)
            )
            if msg and isinstance(getattr(msg, "message_id", None), int):
                t["countdown_message_id"] = msg.message_id
                await db.save("tournaments", tournaments)
        except Exception as e:
            logger.error(f"Failed to send countdown message: {e}")

        # Spawn countdown background worker
        task = asyncio.create_task(cls._countdown_worker(tournament_id, bot_instance, group_chat_id))
        cls._running_countdowns[tournament_id] = task
        return True, "120-second countdown started!"

    @classmethod
    async def force_start(
        cls,
        tournament_id: str,
        bot_instance,
        actor_id: int,
        actor_username: str,
        is_group_admin: bool = False
    ) -> Tuple[bool, str]:
        """
        Immediately ends the countdown and launches the solo tournament.
        Restricted ONLY to group admins and @prathamesh63 / Super Admins.
        """
        tournaments = await db.load("tournaments")
        t = tournaments.get(tournament_id)
        if not t:
            return False, "Tournament not found."

        if t.get("mode") != "solo":
            return False, "Force start is only for Solo Tournaments."

        if t.get("status") not in ["registration", "countdown"]:
            return False, f"Tournament is already {t.get('status')}."

        from bot.middlewares.auth_middleware import is_admin_user
        if not is_group_admin and not await is_admin_user(actor_id, actor_username):
            return False, "Only Group Admins or Bot Admins can force start!"

        participants = await TournamentService.get_tournament_participants(tournament_id)
        if len(participants) < 2:
            return False, "Need at least 2 registered players to force start!"

        # Cancel active countdown worker if running
        task = cls._running_countdowns.pop(tournament_id, None)
        if task and not task.done():
            task.cancel()

        try:
            await bot_instance.send_message(
                chat_id=t["group_chat_id"],
                text=f"⚡ <b>FORCE START!</b>\n🏆 <b>{t['name']}</b> launched early by @{actor_username}!",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send force start notice: {e}")

        await cls._launch_solo_tournament(tournament_id, bot_instance)
        return True, "Tournament force started!"

    @classmethod
    async def cancel_countdown(cls, tournament_id: str, bot_instance, admin_id: int) -> Tuple[bool, str]:
        if tournament_id in cls._running_countdowns:
            cls._running_countdowns[tournament_id].cancel()
            del cls._running_countdowns[tournament_id]

        tournaments = await db.load("tournaments")
        t = tournaments.get(tournament_id)
        if not t:
            return False, "Tournament not found."

        t["status"] = "registration"
        t["countdown_end_time"] = None
        await db.save("tournaments", tournaments)

        try:
            await bot_instance.send_message(
                chat_id=t["group_chat_id"],
                text=f"⚠️ Solo Tournament <b>{t['name']}</b> countdown was cancelled by an admin.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        return True, "Countdown cancelled."

    @classmethod
    async def recover_active_countdowns(cls, bot_instance):
        """
        Invoked on bot startup: resumes any countdown that was interrupted by a restart.
        """
        tournaments = await db.load("tournaments")
        now = time.time()
        for t_id, t in tournaments.items():
            if t.get("mode") == "solo" and t.get("status") == "countdown":
                end_time = t.get("countdown_end_time", 0)
                if end_time > now:
                    logger.info(f"Recovering solo tournament countdown for {t_id}. Remaining: {int(end_time - now)}s")
                    task = asyncio.create_task(cls._countdown_worker(t_id, bot_instance, t["group_chat_id"]))
                    cls._running_countdowns[t_id] = task
                else:
                    logger.info(f"Countdown expired during downtime for {t_id}. Launching immediately...")
                    await cls._launch_solo_tournament(t_id, bot_instance)

    @classmethod
    async def _countdown_worker(cls, tournament_id: str, bot_instance, group_chat_id: int):
        # Broadcast milestones (every 30s: 90, 60, 30, plus final 10s countdown)
        milestones = [90, 60, 30, 10, 5, 4, 3, 2, 1]
        thirty_sec_milestones = {90, 60, 30}
        notified = set()

        try:
            while True:
                tournaments = await db.load("tournaments")
                t = tournaments.get(tournament_id)
                if not t or t.get("status") != "countdown":
                    break

                end_time = t.get("countdown_end_time", 0)
                remaining = int(end_time - time.time())

                if remaining <= 0:
                    break

                for m in milestones:
                    if remaining <= m and m not in notified:
                        notified.add(m)
                        mins, secs = divmod(m, 60)
                        time_str = f"{mins:02d}:{secs:02d}"

                        if m in thirty_sec_milestones:
                            participants = await TournamentService.get_tournament_participants(tournament_id)
                            player_lines = "\n".join(
                                [f"{i}. <b>{p['username'].lstrip('@')}</b>" for i, p in enumerate(participants, 1)]
                            ) or "None yet"
                            text = (
                                f"⏳ <b>{time_str} REMAINING!</b>\n\n"
                                f"🏆 <b>{t['name']}</b>\n"
                                f"👥 <b>Joined Players ({len(participants)}):</b>\n"
                                f"{player_lines}"
                            )
                            reply_markup = get_tournament_register_keyboard(tournament_id)
                        else:
                            text = f"⏳ Tournament starts in <b>{time_str}</b>!"
                            reply_markup = None

                        try:
                            await bot_instance.send_message(
                                chat_id=group_chat_id,
                                text=text,
                                reply_markup=reply_markup,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Error sending milestone {m}: {e}")
                        break

                await asyncio.sleep(1)

            # Launch tournament
            await cls._launch_solo_tournament(tournament_id, bot_instance)

        except asyncio.CancelledError:
            logger.info(f"Countdown for tournament {tournament_id} was cancelled.")
        finally:
            cls._running_countdowns.pop(tournament_id, None)

    @classmethod
    async def _launch_solo_tournament(cls, tournament_id: str, bot_instance):
        tournaments = await db.load("tournaments")
        t = tournaments.get(tournament_id)
        if not t:
            return

        participants = await TournamentService.get_tournament_participants(tournament_id)
        if len(participants) < 2:
            t["status"] = "registration"
            t["countdown_end_time"] = None
            await db.save("tournaments", tournaments)
            try:
                await bot_instance.send_message(
                    chat_id=t["group_chat_id"],
                    text="❌ Tournament could not start: fewer than 2 participants registered.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return

        t["status"] = "active"
        t["started_at"] = time.time()
        t["current_round"] = 1
        t["round_name"] = "Round 1"

        fixtures, byes = TournamentService.generate_single_elimination_bracket(participants, shuffle=True)
        t["round_fixtures"] = fixtures
        t["round_byes"] = byes
        t["round_winners"] = []
        t["current_fixture_index"] = 0
        await db.save("tournaments", tournaments)

        # Announce bracket in group
        bye_text = ""
        if byes:
            bye_names = ", ".join([f"@{b['username']}" for b in byes])
            bye_text = f"\n🎟️ <b>Byes to Next Round:</b> {bye_names}\n"

        bracket_text = f"🚀 <b>SOLO TOURNAMENT HAS BEGUN!</b>\n\n🏆 <b>{t['name']}</b>\n👥 <b>Round 1 Fixtures:</b>\n"
        for idx, f in enumerate(fixtures, 1):
            bracket_text += f"{idx}. @{f['player1']['username']} VS @{f['player2']['username']}\n"
        bracket_text += bye_text + "\n🔥 <i>Starting Match 1 automatically!</i>"

        try:
            await bot_instance.send_message(chat_id=t["group_chat_id"], text=bracket_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to announce tournament start: {e}")

        # Start the first fixture
        from bot.services.game_service import GameService
        await GameService.start_solo_match_fixture(tournament_id, 0, bot_instance)
