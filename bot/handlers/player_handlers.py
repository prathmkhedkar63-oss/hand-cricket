import time
import uuid
import random
import re
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database.json_manager import db
from bot.services.stats_service import StatsService
from bot.services.tournament_service import TournamentService
from bot.services.solo_tournament_service import SoloTournamentService
from bot.services.game_service import GameService
from bot.middlewares.auth_middleware import is_admin_user
from game_engine.models import MatchStatus
from game_engine.scoreboard import ScoreboardFormatter
from bot.keyboards.game_keyboards import (
    get_tournament_register_keyboard,
    get_group_start_keyboard,
    get_claim_host_keyboard,
    get_toss_call_keyboard,
    get_toss_choice_keyboard
)

router = Router(name="player_handlers")

# Bounded in-memory toss state: toss_id -> dict
_active_tosses: dict = {}

async def has_active_group_session(chat_id: int) -> bool:
    tournaments = await db.load("tournaments")
    for t in tournaments.values():
        if t.get("group_chat_id") == chat_id and t.get("status") in ["registration", "countdown", "active"]:
            return True
    for m in GameService.active_matches.values():
        if m.group_chat_id == chat_id and m.status in [MatchStatus.IN_PROGRESS, MatchStatus.PAUSED, MatchStatus.INNINGS_BREAK]:
            return True
    return False

async def is_group_admin_or_super(bot: Bot, chat_id: int, user_id: int, username: str = "") -> bool:
    if await is_admin_user(user_id, username):
        return True
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    from bot.services.media_service import MediaService
    user = message.from_user
    username = (user.username or f"player_{user.id}").lstrip("@")
    await StatsService.get_or_create_user(user.id, username, user.first_name)

    # In a group chat: Prevent double-start if a tournament/match is already active!
    if message.chat.type in ["group", "supergroup"]:
        if await has_active_group_session(message.chat.id):
            await message.answer(
                "⚠️ <b>A tournament or match is already ongoing in this group!</b>\n"
                "Finish it first or a group admin can cancel it with /cancel.",
                parse_mode="HTML"
            )
            return

        keyboard = get_group_start_keyboard()
        text = (
            f"🏏 <b>JPL CRICKET BOT</b>\n\n"
            f"Welcome <b>{username}</b>! Choose how you would like to play:\n"
            f"• <b>Start Solo:</b> Automated 120s knockout (Numbers 1–6, 60s timer)\n"
            f"• <b>Start Tournament:</b> Host-managed Team A vs Team B\n"
            f"• Or type /challenge_bot for an instant 1v1 vs Bot!"
        )
        await MediaService.send_with_image(bot, message.chat.id, "welcome", text, reply_markup=keyboard)
        return

    # In private chat: Welcome message and command overview
    text = (
        f"🏏 <b>WELCOME TO JPL CRICKET BOT!</b>\n\n"
        f"Hello, <b>{username}</b>! You are registered and ready to play.\n\n"
        f"🎮 <b>HOW TO PLAY:</b>\n"
        f"• <b>Bowler</b> types a number privately here in Bot DM.\n"
        f"• <b>Batsman</b> types a number in the group (or here in 1v1 DM).\n"
        f"• Match numbers ➡️ <b>OUT!</b> Differ ➡️ Batsman scores runs!\n\n"
        f"📌 <b>COMMANDS:</b>\n"
        f"• /challenge_bot - Play 1v1 vs Smart Bot\n"
        f"• /profile | /stats | /history\n"
        f"• /leaderboard | /tournaments | /rules\n"
        f"• /help | /about"
    )
    await MediaService.send_with_image(bot, message.chat.id, "welcome", text)

# Group Start Menu Callbacks
@router.callback_query(F.data == "menu:start_solo")
async def on_menu_start_solo(callback: CallbackQuery, bot: Bot):
    chat_id = callback.message.chat.id
    if await has_active_group_session(chat_id):
        await callback.answer("⚠️ A game or tournament is already active in this group!", show_alert=True)
        return

    user = callback.from_user
    username = user.username or f"player_{user.id}"

    t_id = f"solo_{uuid.uuid4().hex[:6]}"
    t_name = f"Solo Knockout Cup #{t_id[-4:]}"

    # Create solo tournament in this group
    await TournamentService.create_tournament(
        tournament_id=t_id,
        name=t_name,
        description="Automated 120s solo tournament (1-6)",
        mode="solo",
        group_chat_id=chat_id,
        creator_id=user.id,
        max_balls=36
    )

    # Auto-register creator
    await TournamentService.register_player(t_id, user.id, username)

    # Launch 120-second countdown (sends the single announcement + Join/Withdraw/Force Start keyboard)
    await SoloTournamentService.start_countdown(t_id, bot, chat_id)
    await callback.answer("Solo tournament countdown initiated!", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "menu:start_tourn")
async def on_menu_start_tourn(callback: CallbackQuery, bot: Bot):
    chat_id = callback.message.chat.id
    if await has_active_group_session(chat_id):
        await callback.answer("⚠️ A game or tournament is already active in this group!", show_alert=True)
        return

    user = callback.from_user
    username = user.username or f"player_{user.id}"

    t_id = f"tourn_{uuid.uuid4().hex[:6]}"
    t_name = f"Championship Trophy #{t_id[-4:]}"

    # Create host tournament in this group (host not yet claimed)
    await TournamentService.create_tournament(
        tournament_id=t_id,
        name=t_name,
        description="Host-managed Team A vs Team B tournament",
        mode="host",
        group_chat_id=chat_id,
        creator_id=user.id,
        host_id=None,
        max_balls=36
    )

    await callback.answer("Host Tournament created! Claim host role below.", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Present [I AM THE HOST] button cleanly (no internal IDs, no @ pings)
    from bot.services.media_service import MediaService
    keyboard = get_claim_host_keyboard(t_id)
    text = (
        f"🏆 <b>JPL CRICKET BOT • HOST TOURNAMENT</b>\n\n"
        f"🏆 <b>{t_name}</b>\n"
        f"Mode: <b>Team A vs Team B</b>\n"
        f"Created by: <b>{username.lstrip('@')}</b>\n\n"
        f"👉 <i>Tap below to claim host controls:</i>"
    )
    await MediaService.send_with_image(bot, chat_id, "match_start", text, reply_markup=keyboard)

@router.callback_query(F.data == "menu:cancel")
async def on_menu_cancel(callback: CallbackQuery):
    await callback.answer("Cancelled.")
    try:
        await callback.message.delete()
    except Exception:
        pass

# Direct commands: /start_solo, /start_tournament, and /cancel
@router.message(Command("start_solo"))
async def cmd_start_solo_direct(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type in ["group", "supergroup"] and await has_active_group_session(chat_id):
        await message.answer("⚠️ A tournament or match is already active in this group! Use /cancel first.")
        return

    user = message.from_user
    username = user.username or f"player_{user.id}"

    args = message.text.split(maxsplit=1)
    t_id = f"solo_{uuid.uuid4().hex[:6]}"
    t_name = args[1] if len(args) > 1 else f"Solo Cup #{t_id[-4:]}"

    await TournamentService.create_tournament(
        tournament_id=t_id,
        name=t_name,
        description="Automated solo tournament (1-6)",
        mode="solo",
        group_chat_id=chat_id,
        creator_id=user.id,
        max_balls=36
    )
    await TournamentService.register_player(t_id, user.id, username)
    await SoloTournamentService.start_countdown(t_id, bot, chat_id)

@router.message(Command("start_tournament"))
async def cmd_start_tournament_direct(message: Message, bot: Bot):
    from bot.services.media_service import MediaService
    chat_id = message.chat.id
    if message.chat.type in ["group", "supergroup"] and await has_active_group_session(chat_id):
        await message.answer("⚠️ A tournament or match is already active in this group! Use /cancel first.")
        return

    user = message.from_user
    username = (user.username or f"player_{user.id}").lstrip("@")

    args = message.text.split(maxsplit=1)
    t_id = f"tourn_{uuid.uuid4().hex[:6]}"
    t_name = args[1] if len(args) > 1 else f"Premier Trophy #{t_id[-4:]}"

    await TournamentService.create_tournament(
        tournament_id=t_id,
        name=t_name,
        description="Host-managed tournament",
        mode="host",
        group_chat_id=chat_id,
        creator_id=user.id,
        host_id=None,
        max_balls=36
    )

    keyboard = get_claim_host_keyboard(t_id)
    text = (
        f"🏆 <b>JPL CRICKET BOT • HOST TOURNAMENT</b>\n\n"
        f"🏆 <b>{t_name}</b>\n"
        f"Created by: <b>{username}</b>\n\n"
        f"👉 <i>Tap below to claim host controls:</i>"
    )
    await MediaService.send_with_image(bot, chat_id, "match_start", text, reply_markup=keyboard)

@router.message(Command("cancel"))
async def cmd_cancel_group_tournament(message: Message, bot: Bot):
    """
    Cancels all ongoing tournaments and matches in the current group,
    or cancels an active 1v1 /challenge_bot match in private DM.
    """
    user = message.from_user
    chat_id = message.chat.id

    if message.chat.type == "private":
        matches_db = await db.load("matches")
        cancelled = []
        for mid in [k for k, m in GameService.active_matches.items() if m.group_chat_id == chat_id]:
            m = GameService.active_matches.pop(mid, None)
            if m:
                GameService.cleanup_match_cache(mid)
                m.status = MatchStatus.ABANDONED
                m.result_text = f"Cancelled by @{user.username or user.id}"
                matches_db[mid] = m.model_dump()
                cancelled.append(m)
        if not cancelled:
            await message.answer("ℹ️ You have no active match in DM.")
            return
        await GameService.flush_pending_balls()
        await db.save("matches", matches_db)
        for m in cancelled:
            await message.answer(ScoreboardFormatter.format_live_scoreboard(m), parse_mode="HTML")
        await message.answer("🛑 Your DM match has been cancelled.")
        return

    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("This command is for cancelling ongoing tournaments/matches in a group or DM.")
        return
    if not await is_group_admin_or_super(bot, message.chat.id, user.id, user.username or ""):
        await message.answer("🚫 Only Group Admins or Bot Admins can cancel ongoing tournaments or matches!")
        return

    chat_id = message.chat.id
    cancelled_tournaments = 0
    cancelled_matches = []

    # 1. Cancel ongoing tournaments in this group
    tournaments = await db.load("tournaments")
    for tid, t in tournaments.items():
        if t.get("group_chat_id") == chat_id and t.get("status") in ["registration", "countdown", "active"]:
            t["status"] = "cancelled"
            t["countdown_end_time"] = None
            task = SoloTournamentService._running_countdowns.pop(tid, None)
            if task and not task.done():
                task.cancel()
            cancelled_tournaments += 1

    if cancelled_tournaments:
        await db.save("tournaments", tournaments)

    # 2. Cancel ongoing matches in this group & display their scorecards
    matches_db = await db.load("matches")
    active_ids = [
        mid for mid, m in GameService.active_matches.items()
        if m.group_chat_id == chat_id
    ]
    for mid in active_ids:
        match = GameService.active_matches.pop(mid, None)
        if match:
            GameService.cancel_turn_timer(mid)
            match.status = MatchStatus.ABANDONED
            match.result_text = f"Cancelled by @{user.username or user.id}"
            matches_db[mid] = match.model_dump()
            cancelled_matches.append(match)

    if cancelled_matches:
        await GameService.flush_pending_balls()
        await db.save("matches", matches_db)

    if cancelled_tournaments == 0 and not cancelled_matches:
        await message.answer("ℹ️ No ongoing tournaments or matches found in this group.")
        return

    for m in cancelled_matches:
        GameService.cleanup_match_cache(m.match_id)
        sb = ScoreboardFormatter.format_live_scoreboard(m)
        await message.answer(sb, parse_mode="HTML")

    await message.answer(
        f"🛑 <b>CANCELLED BY ADMIN</b>\n\n"
        f"• Cancelled Tournaments: <b>{cancelled_tournaments}</b>\n"
        f"• Cancelled Matches: <b>{len(cancelled_matches)}</b>\n"
        f"• Action by: @{user.username or user.id}",
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        f"📖 <b>HAND CRICKET BOT - COMMAND LIST & GUIDE</b>\n\n"
        f"🏏 <b>PLAYER COMMANDS:</b>\n"
        f"• /start - Register player & check bot status\n"
        f"• /help - Show this complete command list\n"
        f"• /profile - View your profile and win rate\n"
        f"• /stats - Career stats (runs, avg, streaks)\n"
        f"• /history - Your recent match results\n"
        f"• /leaderboard - Global rankings & top performers\n"
        f"• /tournaments - View tournaments available in this chat\n"
        f"• /mytournaments - View your joined tournaments\n"
        f"• /rules - Hand cricket game rules\n\n"
        f"🛡️ <b>HOST COMMANDS:</b>\n"
        f"• /host - Open interactive Host Control Panel\n"
        f"• /add_a - Add players to Team A (max 11)\n"
        f"• /add_b - Add players to Team B (max 11)\n"
        f"• /remove_a - Remove players from Team A\n"
        f"• /remove_b - Remove players from Team B\n"
        f"• /swap - Substitute a player by roster number\n"
        f"• /cap_a - Set Team A Captain\n"
        f"• /cap_b - Set Team B Captain\n"
        f"• /overs - Set match overs limit\n"
        f"• /teams - View team rosters & captains\n"
        f"• /start_match - Launch Team A vs Team B match\n"
        f"• /appoint_bowler - Appoint replacement bowler\n"
        f"• /appoint_batsman - Appoint replacement batsman\n"
        f"• /hosttournaments - View your assigned tournaments\n"
        f"• /hostplayers - View tournament players\n"
        f"• /hostmatches - View recent matches\n"
        f"• /hostannounce - Send group announcement\n"
        f"• /setgroup - Bind tournament to current group\n\n"
        f"👑 <b>ADMIN COMMANDS:</b>\n"
        f"• /admin - Open Admin Dashboard\n"
        f"• /createtournament - Create tournament\n"
        f"• /startsolo - Start 120s solo countdown\n"
        f"• /cancelsolo - Cancel countdown\n"
        f"• /cancel - Cancel ongoing group tournament/match\n"
        f"• /players - View registered players\n"
        f"• /hosts - Manage authorized hosts\n"
        f"• /matches - View all system matches\n"
        f"• /systemstats - Real-time system telemetry\n"
        f"• /start_bot - Enable bot\n"
        f"• /stop_bot - Pause bot\n\n"
        f"💡 <i>Any group can be an arena! Use /setgroup inside any group to play tournaments there.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("toss"))
async def cmd_toss(message: Message):
    """
    Interactive Coin Toss & Bat/Bowl choice (/toss [@opponent] or reply).
    """
    now = time.time()
    # Prune stale tosses (> 5 mins) to keep memory minimal
    stale = [k for k, v in _active_tosses.items() if now - v["created_at"] > 300]
    for k in stale:
        _active_tosses.pop(k, None)

    caller = message.from_user
    caller_name = caller.username or f"player_{caller.id}"

    opp_id = None
    opp_name = None
    if message.reply_to_message and message.reply_to_message.from_user:
        opp = message.reply_to_message.from_user
        opp_id = opp.id
        opp_name = opp.username or f"player_{opp.id}"
    else:
        mentions = re.findall(r"@([a-zA-Z0-9_]{3,32})", message.text or "")
        if mentions:
            opp_name = mentions[0]
            users = await db.load("users")
            for uid, u in users.items():
                if u.get("username", "").lower() == opp_name.lower():
                    opp_id = int(uid)
                    break

    toss_id = uuid.uuid4().hex[:6]
    _active_tosses[toss_id] = {
        "toss_id": toss_id,
        "caller_id": caller.id,
        "caller_name": caller_name,
        "opp_id": opp_id,
        "opp_name": opp_name,
        "winner_id": None,
        "winner_name": None,
        "created_at": now
    }

    vs_line = f"⚔️ <b>@{caller_name}</b> VS <b>@{opp_name}</b>\n\n" if opp_name else ""
    keyboard = get_toss_call_keyboard(toss_id)
    await message.answer(
        f"🪙 <b>COIN TOSS!</b>\n\n"
        f"{vs_line}"
        f"@{caller_name}, call <b>Heads</b> or <b>Tails</b>:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("toss_call:"))
async def on_toss_call(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid toss.", show_alert=True)
        return
    toss_id, call = parts[1], parts[2]
    toss = _active_tosses.get(toss_id)
    if not toss:
        await callback.answer("This toss has expired.", show_alert=True)
        return

    if callback.from_user.id != toss["caller_id"]:
        await callback.answer(f"Only @{toss['caller_name']} can call Heads or Tails!", show_alert=True)
        return

    outcome = random.choice(["heads", "tails"])
    caller_won = (call == outcome)

    if caller_won:
        toss["winner_id"] = toss["caller_id"]
        toss["winner_name"] = toss["caller_name"]
    elif toss["opp_name"]:
        toss["winner_id"] = toss["opp_id"]
        toss["winner_name"] = toss["opp_name"]
    else:
        toss["winner_id"] = toss["caller_id"]
        toss["winner_name"] = toss["caller_name"]

    await callback.answer(f"It's {outcome.upper()}!")

    if not caller_won and not toss["opp_name"]:
        _active_tosses.pop(toss_id, None)
        await callback.message.edit_text(
            f"🪙 <b>COIN TOSS RESULT!</b>\n\n"
            f"@{toss['caller_name']} called <b>{call.upper()}</b>.\n"
            f"Coin landed on: <b>{outcome.upper()}</b>!\n\n"
            f"❌ @{toss['caller_name']} lost the toss.",
            parse_mode="HTML"
        )
        return

    keyboard = get_toss_choice_keyboard(toss_id)
    await callback.message.edit_text(
        f"🪙 <b>COIN TOSS RESULT!</b>\n\n"
        f"@{toss['caller_name']} called <b>{call.upper()}</b>.\n"
        f"Coin landed on: <b>{outcome.upper()}</b>!\n\n"
        f"🎉 <b>@{toss['winner_name']}</b> won the toss!\n"
        f"Choose to <b>Bat First</b> or <b>Bowl First</b>:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("toss_pick:"))
async def on_toss_pick(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid choice.", show_alert=True)
        return
    toss_id, choice = parts[1], parts[2]
    toss = _active_tosses.get(toss_id)
    if not toss:
        await callback.answer("This toss has expired.", show_alert=True)
        return

    uid = callback.from_user.id
    uname = (callback.from_user.username or "").lower()
    is_winner = (toss["winner_id"] and uid == toss["winner_id"]) or (not toss["winner_id"] and uname == toss["winner_name"].lower())
    if not is_winner:
        await callback.answer(f"Only @{toss['winner_name']} can choose Bat or Bowl!", show_alert=True)
        return

    _active_tosses.pop(toss_id, None)
    action_str = "BAT FIRST 🏏" if choice == "bat" else "BOWL FIRST 🎯"
    await callback.answer(f"Elected to {choice} first!")

    if toss["opp_name"]:
        other_name = toss["opp_name"] if toss["winner_name"] == toss["caller_name"] else toss["caller_name"]
        bat_first = toss["winner_name"] if choice == "bat" else other_name
        bowl_first = other_name if choice == "bat" else toss["winner_name"]
        extra = f"\n\n🏏 Batting 1st: @{bat_first}\n🎯 Bowling 1st: @{bowl_first}\n<i>Host can start with:</i> <code>/start_match @{bat_first} @{bowl_first}</code>"
    else:
        extra = ""

    await callback.message.edit_text(
        f"🪙 <b>TOSS DECISION!</b>\n\n"
        f"🏆 <b>@{toss['winner_name']}</b> won the toss and elected to <b>{action_str}</b>!{extra}",
        parse_mode="HTML"
    )

@router.message(Command("challenge_bot"))
async def cmd_challenge_bot(message: Message, bot: Bot):
    """
    Starts a 1v1 match against the pure-logic BotPsychologyEngine in either a group or private DM!
    """
    from game_engine.bot_ai import BotPsychologyEngine

    chat_id = message.chat.id
    user = message.from_user
    username = user.username or f"player_{user.id}"
    is_group = message.chat.type in ["group", "supergroup"]

    if is_group and await has_active_group_session(chat_id):
        await message.answer("⚠️ A tournament or match is already active in this group! Use /cancel first.")
        return

    if not is_group:
        for m in GameService.active_matches.values():
            if m.group_chat_id == chat_id and m.status == MatchStatus.IN_PROGRESS:
                await message.answer("⚠️ You already have an active match in this chat!")
                return

    # Optional overs argument (default 2 overs = 12 balls)
    args = (message.text or "").split()
    overs = 2
    if len(args) > 1 and args[1].isdigit():
        overs = max(1, min(10, int(args[1])))

    match_id = f"bot1v1_{uuid.uuid4().hex[:6]}"
    # Randomize who bats first
    if random.choice([True, False]):
        p1_id, p1_name = user.id, username
        p2_id, p2_name = BotPsychologyEngine.BOT_USER_ID, BotPsychologyEngine.BOT_USERNAME
    else:
        p1_id, p1_name = BotPsychologyEngine.BOT_USER_ID, BotPsychologyEngine.BOT_USERNAME
        p2_id, p2_name = user.id, username

    await GameService.start_new_match(
        match_id=match_id,
        player1_id=p1_id,
        player1_username=p1_name,
        player2_id=p2_id,
        player2_username=p2_name,
        group_chat_id=chat_id,
        bot=bot,
        tournament_id=None,
        round_name=f"1v1 vs Bot ({overs} Ov)",
        max_balls=overs * 6,
        wickets=1,
        mode="host",
        min_number=0,
        max_number=6
    )

@router.message(Command("score"))
async def cmd_live_score(message: Message, bot: Bot):
    """
    Anyone in the group can view the current live scorecard image + summary on demand via /score.
    """
    if not GameService.active_matches:
        await GameService.recover_active_matches()

    chat_id = message.chat.id
    target_match = None
    for m in GameService.active_matches.values():
        if m.group_chat_id == chat_id:
            target_match = m
            break

    if not target_match:
        await message.answer("ℹ️ No live match is currently active in this chat.")
        return

    sb = ScoreboardFormatter.format_live_scoreboard(target_match)
    inn_obj = target_match.first_innings if target_match.current_innings == 1 else target_match.second_innings
    if inn_obj:
        try:
            from game_engine.scoreboard_image import ScoreboardImageGenerator
            img_bytes = ScoreboardImageGenerator.render_over_card(
                target_match,
                inn_obj,
                title_override=f"LIVE SCORECARD • INN {inn_obj.innings_num}"
            )
            await MediaService.send_generated_image(bot, chat_id, img_bytes, "live_scorecard.jpg", sb)
            return
        except Exception:
            pass
    await message.answer(sb, parse_mode="HTML")

@router.message(Command("about"))
async def cmd_about(message: Message):
    text = (
        f"ℹ️ <b>ABOUT JPL CRICKET BOT</b>\n\n"
        f"🏏 <b>Advanced Hand Cricket & Tournament System</b>\n"
        f"⚡ Private DM Bowling + Group Batting + Smart 1v1 Bot\n"
        f"🏆 Automated Solo Knockouts & Host-Managed Team Leagues\n\n"
        f"👨‍💻 <b>Made by @prathamesh63</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("rules"))
async def cmd_rules(message: Message):
    text = (
        f"📜 <b>HAND CRICKET GAME RULES</b>\n\n"
        f"• Available numbers: <b>0, 1, 2, 3, 4, 5, 6</b>\n"
        f"• <b>Dismissal (WICKET):</b> If batsman and bowler select identical numbers, batsman is OUT.\n"
        f"• <b>Scoring:</b> If numbers differ, batsman adds their selected number to total score.\n"
        f"• <b>2 Innings:</b> Both players alternate batting and bowling.\n"
        f"• <b>Target:</b> Second innings player chases (First Innings Score + 1).\n"
        f"• <b>Victory:</b> Reaching target wins the match for the chasing team. Getting bowled out before target gives victory to the first batsman.\n"
        f"• <b>Tie:</b> If balls run out and scores are equal."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    user = await db.get("users", str(user_id))
    stats = await db.get("statistics", str(user_id), {})

    if not user:
        await message.answer("Please type /start to register.")
        return

    reg_date = datetime.fromtimestamp(user.get("registered_at", time.time())).strftime("%Y-%m-%d")
    username = user.get("username", f"player_{user_id}")

    text = (
        f"👤 <b>PLAYER PROFILE</b>\n\n"
        f"🏷️ Username: <b>@{username}</b>\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"📅 Registered: {reg_date}\n"
        f"⚔️ Matches: {stats.get('matches_played', 0)} (Won: {stats.get('matches_won', 0)} | Lost: {stats.get('matches_lost', 0)})\n"
        f"🏏 Total Runs: {stats.get('total_runs', 0)}\n"
        f"🔥 Win Rate: {stats.get('win_percentage', 0.0)}%\n"
        f"⚡ Current Streak: {stats.get('current_streak', 0)} wins\n"
        f"🏆 Tournaments Won: {stats.get('tournament_victories', 0)}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    stats = await db.get("statistics", str(user_id))
    if not stats:
        await message.answer("No statistics found. Play your first match to generate stats!")
        return

    text = (
        f"📊 <b>CRICKET CAREER STATISTICS</b>\n\n"
        f"👤 Player: <b>@{stats.get('username', f'player_{user_id}')}</b>\n\n"
        f"⚔️ <b>Matches:</b> {stats.get('matches_played', 0)}\n"
        f"✅ <b>Won:</b> {stats.get('matches_won', 0)}\n"
        f"❌ <b>Lost:</b> {stats.get('matches_lost', 0)}\n"
        f"🤝 <b>Drawn:</b> {stats.get('matches_drawn', 0)}\n\n"
        f"🏏 <b>Total Runs:</b> {stats.get('total_runs', 0)}\n"
        f"🌟 <b>Highest Score:</b> {stats.get('highest_score', 0)}\n"
        f"🔴 <b>Total Dismissals:</b> {stats.get('total_dismissals', 0)}\n"
        f"📈 <b>Batting Average:</b> {stats.get('batting_average', 0.0)}\n"
        f"🎯 <b>Win Percentage:</b> {stats.get('win_percentage', 0.0)}%\n\n"
        f"🔥 <b>Current Streak:</b> {stats.get('current_streak', 0)}\n"
        f"⚡ <b>Highest Streak:</b> {stats.get('highest_streak', 0)}\n"
        f"🏆 <b>Tournaments Won:</b> {stats.get('tournament_victories', 0)}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("history"))
async def cmd_history(message: Message):
    user_id = message.from_user.id
    matches_db = await db.load("matches")
    user_matches = []

    for m in matches_db.values():
        if m.get("player1_id") == user_id or m.get("player2_id") == user_id:
            user_matches.append(m)

    if not user_matches:
        await message.answer("No match history found.")
        return

    # Recent 5 matches
    user_matches.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    text = "📜 <b>RECENT MATCH HISTORY</b>\n\n"
    for m in user_matches[:5]:
        p1 = f"@{m.get('player1_username')}"
        p2 = f"@{m.get('player2_username')}"
        status = m.get("status")
        result = m.get("result_text") or status
        text += f"• <b>{p1} vs {p2}</b>\n  Outcome: {result}\n\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    await StatsService.refresh_leaderboards()
    lb = await db.load("leaderboard")
    wins_list = lb.get("global_wins", [])[:10]

    text = "🏆 <b>GLOBAL LEADERBOARD (MOST WINS)</b>\n\n"
    if not wins_list:
        text += "No match records yet. Be the first to win a match!"
    else:
        for idx, p in enumerate(wins_list, 1):
            text += f"{idx}. <b>@{p['username']}</b> – {p['matches_won']} Wins ({p['total_runs']} Runs)\n"

    # Category buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Wins", callback_data="lb:wins"),
            InlineKeyboardButton(text="🏏 Runs", callback_data="lb:runs")
        ],
        [
            InlineKeyboardButton(text="🌟 High Score", callback_data="lb:high"),
            InlineKeyboardButton(text="🔥 Win %", callback_data="lb:winpct")
        ],
        [
            InlineKeyboardButton(text="⚡ Streak", callback_data="lb:streak")
        ]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("lb:"))
async def on_leaderboard_category(callback: CallbackQuery):
    cat = callback.data.split(":")[1]
    lb = await db.load("leaderboard")

    if cat == "wins":
        title = "🏆 GLOBAL LEADERBOARD (MOST WINS)"
        items = lb.get("global_wins", [])[:10]
        line_fn = lambda p, i: f"{i}. <b>@{p['username']}</b> – {p['matches_won']} Wins\n"
    elif cat == "runs":
        title = "🏏 HIGHEST RUNS LEADERBOARD"
        items = lb.get("highest_runs", [])[:10]
        line_fn = lambda p, i: f"{i}. <b>@{p['username']}</b> – {p['total_runs']} Runs\n"
    elif cat == "high":
        title = "🌟 HIGHEST INDIVIDUAL SCORE"
        items = lb.get("highest_score", [])[:10]
        line_fn = lambda p, i: f"{i}. <b>@{p['username']}</b> – {p['highest_score']} Runs\n"
    elif cat == "winpct":
        title = "🎯 BEST WIN PERCENTAGE (Min 3 Matches)"
        items = lb.get("best_win_percentage", [])[:10]
        line_fn = lambda p, i: f"{i}. <b>@{p['username']}</b> – {p['win_percentage']}% ({p['matches_won']}/{p['matches_played']})\n"
    elif cat == "streak":
        title = "🔥 LONGEST WINNING STREAK"
        items = lb.get("longest_streak", [])[:10]
        line_fn = lambda p, i: f"{i}. <b>@{p['username']}</b> – {p['longest_streak']} Streak\n"
    else:
        await callback.answer("Invalid category.")
        return

    text = f"<b>{title}</b>\n\n"
    if not items:
        text += "No records available for this category yet."
    else:
        for idx, item in enumerate(items, 1):
            text += line_fn(item, idx)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Wins", callback_data="lb:wins"),
            InlineKeyboardButton(text="🏏 Runs", callback_data="lb:runs")
        ],
        [
            InlineKeyboardButton(text="🌟 High Score", callback_data="lb:high"),
            InlineKeyboardButton(text="🔥 Win %", callback_data="lb:winpct")
        ],
        [
            InlineKeyboardButton(text="⚡ Streak", callback_data="lb:streak")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.message(Command("tournaments"))
async def cmd_tournaments(message: Message):
    tournaments = await db.load("tournaments")
    is_group = message.chat.type in ["group", "supergroup"]
    all_active = [t for t in tournaments.values() if t.get("status") in ["registration", "countdown", "active"]]

    if not all_active:
        await message.answer("No active tournaments currently available. Create one with /createtournament!")
        return

    # In a group: prioritize tournaments specifically linked to this group, or unlinked ones
    if is_group:
        group_t = [t for t in all_active if t.get("group_chat_id") == message.chat.id]
        unlinked = [t for t in all_active if not t.get("group_chat_id")]
        active_list = group_t or unlinked or all_active
    else:
        active_list = all_active

    for t in active_list[:3]:
        parts = await TournamentService.get_tournament_participants(t["tournament_id"])
        mode_str = "Solo Automated" if t["mode"] == "solo" else "Host Controlled"
        arena_info = f"🏟️ Arena: Current Group\n" if t.get("group_chat_id") == message.chat.id else ""
        text = (
            f"🏆 <b>TOURNAMENT: {t['name']}</b>\n\n"
            f"📝 {t.get('description', '')}\n"
            f"⚙️ Mode: <b>{mode_str}</b>\n"
            f"⚡ Status: <b>{t['status'].upper()}</b>\n"
            f"{arena_info}"
            f"👥 Registered: <b>{len(parts)} players</b>"
        )
        keyboard = get_tournament_register_keyboard(t["tournament_id"])
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("mytournaments"))
async def cmd_my_tournaments(message: Message):
    user_id = message.from_user.id
    participants = await db.load("participants")
    my_tids = [p["tournament_id"] for p in participants if p["user_id"] == user_id]

    if not my_tids:
        await message.answer("You have not joined any tournaments yet. Use /tournaments to explore!")
        return

    tournaments = await db.load("tournaments")
    text = "📋 <b>YOUR JOINED TOURNAMENTS</b>\n\n"
    for tid in set(my_tids):
        t = tournaments.get(tid)
        if t:
            text += f"• <b>{t['name']}</b> ({t['mode'].upper()}) - Status: {t['status'].upper()}\n"

    await message.answer(text, parse_mode="HTML")

# Tournament Registration Callbacks
@router.callback_query(F.data.startswith("treg:"))
async def on_tournament_register(callback: CallbackQuery):
    tid = callback.data.split(":")[1]
    success, msg = await TournamentService.register_player(tid, callback.from_user.id, callback.from_user.username or "")
    await callback.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("twid:"))
async def on_tournament_withdraw(callback: CallbackQuery):
    tid = callback.data.split(":")[1]
    success, msg = await TournamentService.withdraw_player(tid, callback.from_user.id)
    await callback.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("tpart:"))
async def on_tournament_view_participants(callback: CallbackQuery):
    tid = callback.data.split(":")[1]
    parts = await TournamentService.get_tournament_participants(tid)
    if not parts:
        await callback.answer("No registered participants yet.", show_alert=True)
        return

    names = "\n".join([f"{idx}. <b>{p['username'].lstrip('@')}</b>" for idx, p in enumerate(parts, 1)])
    await callback.message.reply(f"👥 <b>JOINED PLAYERS ({len(parts)}):</b>\n\n{names}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("tforce:"))
async def on_tournament_force_start(callback: CallbackQuery, bot: Bot):
    tid = callback.data.split(":")[1]
    actor_username = callback.from_user.username or f"player_{callback.from_user.id}"
    is_g_admin = False
    if callback.message and callback.message.chat.type in ["group", "supergroup"]:
        is_g_admin = await is_group_admin_or_super(bot, callback.message.chat.id, callback.from_user.id, actor_username)

    success, msg = await SoloTournamentService.force_start(
        tournament_id=tid,
        bot_instance=bot,
        actor_id=callback.from_user.id,
        actor_username=actor_username,
        is_group_admin=is_g_admin
    )
    await callback.answer(msg, show_alert=not success)
