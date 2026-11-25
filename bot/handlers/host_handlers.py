import time
import uuid
import re
from typing import Optional, Tuple, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database.json_manager import db
from config.settings import settings
from bot.services.host_tournament_service import HostTournamentService
from bot.services.tournament_service import TournamentService
from bot.services.stats_service import StatsService
from bot.services.game_service import GameService
from bot.keyboards.host_keyboards import get_host_dashboard_keyboard
from bot.middlewares.auth_middleware import is_admin_user
from game_engine.models import MatchStatus
from game_engine.scoreboard import ScoreboardFormatter

router = Router(name="host_handlers")

async def check_host_auth(user_id: int, tournament_id: str = None, username: str = None) -> bool:
    if await is_admin_user(user_id, username):
        return True
    return await HostTournamentService.is_host_authorized(user_id, tournament_id)

async def get_active_host_tournament(message: Message) -> Optional[dict]:
    """
    Finds the active host tournament for this group where user is host or admin.
    """
    tournaments = await db.load("tournaments")
    user_id = message.from_user.id
    is_super = (user_id == settings.SUPER_ADMIN_ID)

    # 1. Search for active tournament in this chat
    for tid, t in tournaments.items():
        if t.get("mode") == "host" and t.get("status") in ["registration", "active"]:
            if t.get("group_chat_id") == message.chat.id:
                if is_super or t.get("host_id") == user_id:
                    return t

    # 2. Fallback: most recent host tournament owned by user
    for tid, t in reversed(list(tournaments.items())):
        if t.get("mode") == "host" and t.get("status") in ["registration", "active"]:
            if is_super or t.get("host_id") == user_id:
                return t
    return None

async def resolve_player(message: Message, arg_text: str = "") -> List[Tuple[int, str]]:
    """
    Resolves players from reply_to_message, @mentions, or numeric Telegram IDs.
    """
    resolved = []
    seen_ids = set()

    # 1. Reply to user
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        u_name = target.username or f"player_{target.id}"
        await StatsService.get_or_create_user(target.id, u_name, target.first_name)
        resolved.append((target.id, u_name))
        seen_ids.add(target.id)

    users = await db.load("users")

    # 2. Text @mentions
    mentions = re.findall(r"@([a-zA-Z0-9_]{3,32})", arg_text)
    for m in mentions:
        found_id = None
        for uid, u in users.items():
            if u.get("username", "").lower() == m.lower():
                found_id = int(uid)
                break
        if not found_id:
            found_id = abs(hash(m.lower())) % (10**9)
            await StatsService.get_or_create_user(found_id, m)
        if found_id not in seen_ids:
            resolved.append((found_id, m))
            seen_ids.add(found_id)

    # 3. Numeric Telegram IDs (tokens after the command)
    tokens = arg_text.split()[1:] if arg_text else []
    for tok in tokens:
        if tok.isdigit():
            uid = int(tok)
            if uid not in seen_ids:
                u = users.get(str(uid))
                uname = u.get("username") if u else f"player_{uid}"
                if not u:
                    await StatsService.get_or_create_user(uid, uname)
                resolved.append((uid, uname))
                seen_ids.add(uid)

    return resolved

def format_teams_roster_card(target_t: dict, teams_data: dict) -> str:
    team_a = teams_data.get("Team A", [])
    team_b = teams_data.get("Team B", [])
    captains = teams_data.get("captains", {})

    cap_a = captains.get("Team A", {}).get("username")
    cap_b = captains.get("Team B", {}).get("username")

    cap_a_str = f"👑 Captain: @{cap_a}\n" if cap_a else ""
    cap_b_str = f"👑 Captain: @{cap_b}\n" if cap_b else ""

    idx = 1
    a_lines = []
    for p in team_a:
        a_lines.append(f"{idx}. <b>{p.get('username', '').lstrip('@')}</b>")
        idx += 1
    b_lines = []
    for p in team_b:
        b_lines.append(f"{idx}. <b>{p.get('username', '').lstrip('@')}</b>")
        idx += 1

    team_a_lines = "\n".join(a_lines) if a_lines else "None"
    team_b_lines = "\n".join(b_lines) if b_lines else "None"
    overs = target_t.get("max_balls", 36) // 6
    host_name = (target_t.get("host_username") or "Unassigned").lstrip("@")
    cap_a_str = f"👑 Captain: <b>{cap_a.lstrip('@')}</b>\n" if cap_a else ""
    cap_b_str = f"👑 Captain: <b>{cap_b.lstrip('@')}</b>\n" if cap_b else ""

    return (
        f"📊 <b>JPL CRICKET BOT • {target_t['name']}</b>\n"
        f"⚙️ Overs: <b>{overs} Overs</b> ({target_t.get('max_balls', 36)} balls) | Wickets: 1\n"
        f"🛡️ Host: <b>{host_name}</b>\n\n"
        f"🔴 <b>TEAM A ({len(team_a)}/11):</b>\n"
        f"{cap_a_str}"
        f"{team_a_lines}\n\n"
        f"🔵 <b>TEAM B ({len(team_b)}/11):</b>\n"
        f"{cap_b_str}"
        f"{team_b_lines}\n\n"
        f"<i>Use /start_match to begin or /swap to substitute!</i>"
    )

# --- CLAIM HOST CALLBACK ---
@router.callback_query(F.data.startswith("claim_host:"))
async def on_claim_host(callback: CallbackQuery):
    tid = callback.data.split(":")[1]
    tournaments = await db.load("tournaments")
    t = tournaments.get(tid)
    if not t:
        await callback.answer("Tournament not found.", show_alert=True)
        return

    user = callback.from_user
    username = user.username or f"host_{user.id}"

    # If host already claimed by someone else
    if t.get("host_id") and t.get("host_id") != user.id and user.id != settings.SUPER_ADMIN_ID:
        await callback.answer(f"Host already claimed by @{t.get('host_username', 'another user')}!", show_alert=True)
        return

    # Claim host role
    t["host_id"] = user.id
    t["host_username"] = username
    t["group_chat_id"] = callback.message.chat.id
    await db.save("tournaments", tournaments)

    # Register in hosts database
    await HostTournamentService.assign_host(user.id, username, [tid], assigned_by=user.id)

    announcement = (
        f"🛡️ <b>HOST CLAIMED!</b>\n\n"
        f"<b>@{username}</b> is now the official Host of <b>{t['name']}</b>!\n\n"
        f"📋 <b>HOST COMMANDS:</b>\n"
        f"• /add_a - Add players to Team A (max 11)\n"
        f"• /add_b - Add players to Team B (max 11)\n"
        f"• /remove_a - Remove players from Team A\n"
        f"• /remove_b - Remove players from Team B\n"
        f"• /swap - Substitute a player by roster number\n"
        f"• /cap_a - Set Team A Captain\n"
        f"• /cap_b - Set Team B Captain\n"
        f"• /overs - Set overs per innings\n"
        f"• /teams - View team rosters & captains\n"
        f"• /start_match - Launch the match"
    )
    try:
        await callback.message.edit_text(announcement, parse_mode="HTML")
    except Exception:
        await callback.message.answer(announcement, parse_mode="HTML")

    await callback.answer("You are now the Host!", show_alert=False)

# --- CHAT COMMANDS: /add_a, /add_b, /remove_a, /remove_b, /swap, /cap_a, /cap_b, /overs, /teams, /start_match ---

async def _handle_team_modify(message: Message, team_name: str, action: str):
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found in this group where you are the host.")
        return

    players = await resolve_player(message, message.text)
    if not players:
        cmd = "add" if action == "add" else "remove"
        suffix = "a" if team_name == "Team A" else "b"
        await message.answer(f"Reply to a player or pass players after /{cmd}_{suffix}.")
        return

    tid = t["tournament_id"]
    succeeded = []
    notes = []
    for uid, uname in players:
        ok, msg = await HostTournamentService.manage_teams(tid, team_name, action, uid, uname)
        if ok:
            if action == "add":
                await TournamentService.register_player(tid, uid, uname)
            succeeded.append(f"@{uname}")
        else:
            notes.append(msg)

    teams_data = await HostTournamentService.get_teams(tid)
    roster_card = format_teams_roster_card(t, teams_data)

    icon = "🔴" if team_name == "Team A" else "🔵"
    verb = "Added to" if action == "add" else "Removed from"
    header = f"{icon} <b>{verb} {team_name.upper()}:</b> {', '.join(succeeded)}\n" if succeeded else ""
    note_str = f"⚠️ {' | '.join(notes)}\n" if notes else ""

    await message.answer(f"{header}{note_str}\n{roster_card}", parse_mode="HTML")

@router.message(Command("add_a"))
async def cmd_add_team_a(message: Message):
    await _handle_team_modify(message, "Team A", "add")

@router.message(Command("add_b"))
async def cmd_add_team_b(message: Message):
    await _handle_team_modify(message, "Team B", "add")

@router.message(Command("remove_a"))
async def cmd_remove_team_a(message: Message):
    await _handle_team_modify(message, "Team A", "remove")

@router.message(Command("remove_b"))
async def cmd_remove_team_b(message: Message):
    await _handle_team_modify(message, "Team B", "remove")

@router.message(Command("swap"))
async def cmd_swap_player(message: Message):
    """
    Substitutes a player by their roster number with a new player: /swap <number> <new_player>
    """
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found where you are the host.")
        return

    args = (message.text or "").split()
    slot_num = None
    for tok in args[1:]:
        if tok.isdigit():
            slot_num = int(tok)
            break

    # Resolve new player (via mention or reply; exclude numeric slot token)
    rest_text = " ".join([tok for tok in args[1:] if not (tok.isdigit() and int(tok) == slot_num)])
    players = await resolve_player(message, f"/swap {rest_text}")

    if slot_num is None or not players:
        await message.answer("Provide the roster number and the new player to swap in.")
        return

    new_uid, new_uname = players[0]
    tid = t["tournament_id"]
    ok, msg = await HostTournamentService.swap_player(tid, slot_num, new_uid, new_uname)
    if not ok:
        await message.answer(f"⚠️ {msg}")
        return

    await TournamentService.register_player(tid, new_uid, new_uname)
    teams_data = await HostTournamentService.get_teams(tid)
    roster_card = format_teams_roster_card(t, teams_data)
    await message.answer(f"🔄 <b>{msg}</b>\n\n{roster_card}", parse_mode="HTML")

@router.message(Command("cap_a"))
async def cmd_set_cap_a(message: Message):
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found where you are the host.")
        return

    players = await resolve_player(message, message.text)
    if not players:
        await message.answer("Reply to a player or specify the captain after /cap_a.")
        return

    uid, uname = players[0]
    await HostTournamentService.set_captain(t["tournament_id"], "Team A", uid, uname)
    await message.answer(f"👑 <b>Captain for TEAM A:</b> @{uname}", parse_mode="HTML")

@router.message(Command("cap_b"))
async def cmd_set_cap_b(message: Message):
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found where you are the host.")
        return

    players = await resolve_player(message, message.text)
    if not players:
        await message.answer("Reply to a player or specify the captain after /cap_b.")
        return

    uid, uname = players[0]
    await HostTournamentService.set_captain(t["tournament_id"], "Team B", uid, uname)
    await message.answer(f"👑 <b>Captain for TEAM B:</b> @{uname}", parse_mode="HTML")

@router.message(Command("overs"))
async def cmd_set_overs(message: Message):
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found where you are the host.")
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Specify the number of overs (1-20) after /overs.")
        return

    overs = int(args[1])
    if overs < 1 or overs > 20:
        await message.answer("⚠️ Overs must be between 1 and 20.")
        return

    tournaments = await db.load("tournaments")
    tid = t["tournament_id"]
    tournaments[tid]["max_balls"] = overs * 6
    await db.save("tournaments", tournaments)

    await message.answer(
        f"⚙️ <b>MATCH OVERS CONFIGURED!</b>\n\n"
        f"Overs per innings: <b>{overs} Overs</b> ({overs * 6} Balls)\n"
        f"Tournament: <b>{t['name']}</b>",
        parse_mode="HTML"
    )

@router.message(Command("teams"))
async def cmd_view_teams(message: Message):
    tournaments = await db.load("tournaments")
    target_t = None
    for tid, t in tournaments.items():
        if t.get("mode") == "host" and t.get("status") in ["registration", "active"]:
            if t.get("group_chat_id") == message.chat.id:
                target_t = t
                break

    if not target_t:
        await message.answer("No active host tournament currently open in this group. Start one with /start_tournament!")
        return

    teams_data = await HostTournamentService.get_teams(target_t["tournament_id"])
    text = format_teams_roster_card(target_t, teams_data)
    await message.answer(text, parse_mode="HTML")

@router.message(Command("start_match"))
async def cmd_host_start_match(message: Message, bot: Bot):
    t = await get_active_host_tournament(message)
    if not t:
        await message.answer("⚠️ No active host tournament found where you are the host.")
        return

    tid = t["tournament_id"]
    teams_data = await HostTournamentService.get_teams(tid)
    team_a = teams_data.get("Team A", [])
    team_b = teams_data.get("Team B", [])

    if not team_a or not team_b:
        await message.answer("⚠️ Both Team A and Team B must have at least 1 player registered! Use /add_a and /add_b first.")
        return

    # Check if host passed specific players (e.g. /start_match @batsman @bowler)
    args = message.text.split()
    mentions = re.findall(r"@([a-zA-Z0-9_]{3,32})", message.text)

    p1 = None
    p2 = None

    if len(mentions) >= 2:
        users = await db.load("users")
        for uid, u in users.items():
            if u.get("username", "").lower() == mentions[0].lower():
                p1 = {"user_id": int(uid), "username": u.get("username")}
            elif u.get("username", "").lower() == mentions[1].lower():
                p2 = {"user_id": int(uid), "username": u.get("username")}
    
    # Default: Use captains or first player of each team
    if not p1:
        cap_a = teams_data.get("captains", {}).get("Team A")
        p1 = cap_a if cap_a else team_a[0]
    if not p2:
        cap_b = teams_data.get("captains", {}).get("Team B")
        p2 = cap_b if cap_b else team_b[0]

    match_id = f"hm_{tid}_{uuid.uuid4().hex[:6]}"
    max_balls = t.get("max_balls", 36)

    await GameService.start_new_match(
        match_id=match_id,
        player1_id=p1["user_id"],
        player1_username=p1["username"],
        player2_id=p2["user_id"],
        player2_username=p2["username"],
        group_chat_id=message.chat.id,
        bot=bot,
        tournament_id=tid,
        round_name="Team Match",
        max_balls=max_balls,
        wickets=1
    )

    await message.answer(
        f"🚀 <b>MATCH LAUNCHED!</b>\n\n"
        f"🔴 Team A: <b>@{p1['username']}</b> (Batting 1st)\n"
        f"🔵 Team B: <b>@{p2['username']}</b> (Bowling 1st)\n"
        f"⚙️ Overs: <b>{max_balls // 6} Overs</b>\n\n"
        f"<i>Bowler @{p2['username']} will receive a private prompt in the bot's direct chat!</i>",
        parse_mode="HTML"
    )

@router.message(Command("appoint_bowler"))
async def cmd_appoint_bowler(message: Message, bot: Bot):
    """
    Allows Host, Team Captain, or @prathamesh63 to appoint a new bowler in a host tournament match.
    """
    await _appoint_match_player(message, bot, role="bowler")

@router.message(Command("appoint_batsman"))
async def cmd_appoint_batsman(message: Message, bot: Bot):
    """
    Allows Host, Team Captain, or @prathamesh63 to appoint a new batsman in a host tournament match.
    """
    await _appoint_match_player(message, bot, role="batsman")

async def _appoint_match_player(message: Message, bot: Bot, role: str):
    # Find active or paused match in this group
    target_match = None
    for m in GameService.active_matches.values():
        if m.group_chat_id == message.chat.id:
            target_match = m
            break

    if not target_match:
        await message.answer("⚠️ No active or paused match found in this group.")
        return

    user_id = message.from_user.id
    username = message.from_user.username or ""
    is_authorized = await is_admin_user(user_id, username)

    if not is_authorized and target_match.tournament_id:
        t = await db.get("tournaments", target_match.tournament_id, {})
        if t.get("host_id") == user_id:
            is_authorized = True
        else:
            teams_data = await HostTournamentService.get_teams(target_match.tournament_id)
            captains = teams_data.get("captains", {})
            for cap in captains.values():
                if cap and cap.get("user_id") == user_id:
                    is_authorized = True
                    break

    if not is_authorized:
        await message.answer("🚫 Only the Tournament Host, a Team Captain, or a Bot Admin can appoint a new player!")
        return

    players = await resolve_player(message, message.text)
    if not players:
        await message.answer(f"Usage: <code>/appoint_{role} @username</code> (or reply to user's message)", parse_mode="HTML")
        return

    new_uid, new_uname = players[0]
    target_match.player_warnings[str(new_uid)] = 0

    if role == "bowler":
        target_match.current_bowler_id = new_uid
        target_match.current_bowler_username = new_uname
        target_match.pending_bowler_number = None
        target_match.pending_bowler_ball_id = None
    else:
        target_match.current_batsman_id = new_uid
        target_match.current_batsman_username = new_uname

    target_match.status = MatchStatus.IN_PROGRESS
    await GameService.save_match(target_match)

    await message.answer(
        f"✅ <b>NEW {role.upper()} APPOINTED!</b>\n\n"
        f"👤 @{new_uname} is now the active {role}.\n"
        f"▶️ Match resumed!",
        parse_mode="HTML"
    )
    if role == "bowler":
        await GameService.prompt_bowler(target_match, bot)
    else:
        await GameService.prompt_batsman_in_group(target_match, bot)

# --- Standard host dashboard / admin management ---

@router.message(Command("host"))
async def cmd_host(message: Message):
    user_id = message.from_user.id
    if not await check_host_auth(user_id):
        await message.answer("🚫 You are not registered as an authorized tournament host.")
        return

    tournaments = await db.load("tournaments")
    assigned = []
    for tid, t in tournaments.items():
        if await check_host_auth(user_id, tid):
            assigned.append(t)

    active_tid = assigned[0]["tournament_id"] if assigned else ""
    t_name = assigned[0]["name"] if assigned else "None Selected"

    keyboard = get_host_dashboard_keyboard(active_tid)
    text = (
        f"🛡️ <b>HOST CONTROL DASHBOARD</b>\n\n"
        f"👤 Host: @{message.from_user.username or user_id}\n"
        f"🏆 Selected Tournament: <b>{t_name}</b> (ID: <code>{active_tid or 'none'}</code>)\n"
        f"📋 Total Assigned: {len(assigned)}\n\n"
        f"Select an operation below to manage tournament proceedings:"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("hosttournaments"))
async def cmd_host_tournaments(message: Message):
    user_id = message.from_user.id
    if not await check_host_auth(user_id):
        await message.answer("🚫 Unauthorized.")
        return

    tournaments = await db.load("tournaments")
    text = "🏆 <b>YOUR ASSIGNED TOURNAMENTS</b>\n\n"
    found = 0
    for tid, t in tournaments.items():
        if await check_host_auth(user_id, tid):
            found += 1
            text += f"{found}. <b>{t['name']}</b> ({t['mode'].upper()})\n   ID: <code>{tid}</code> | Status: {t['status'].upper()}\n\n"

    if not found:
        text += "No tournaments assigned to you yet."
    await message.answer(text, parse_mode="HTML")

@router.message(Command("hostplayers"))
async def cmd_host_players(message: Message):
    user_id = message.from_user.id
    if not await check_host_auth(user_id):
        await message.answer("🚫 Unauthorized.")
        return

    tournaments = await db.load("tournaments")
    args = message.text.split()
    tid = args[1] if len(args) > 1 else None

    if not tid:
        for t_key, t in tournaments.items():
            if (message.chat.type in ["group", "supergroup"] and t.get("group_chat_id") == message.chat.id) or await check_host_auth(user_id, t_key):
                tid = t_key
                break

    if not tid:
        await message.answer("Usage: <code>/hostplayers &lt;tournament_id&gt;</code>", parse_mode="HTML")
        return

    parts = await TournamentService.get_tournament_participants(tid)
    text = f"👥 <b>PLAYERS IN TOURNAMENT ({len(parts)}):</b>\n\n"
    if not parts:
        text += "No participants registered yet."
    else:
        for idx, p in enumerate(parts, 1):
            text += f"{idx}. @{p['username']} (ID: <code>{p['user_id']}</code>)\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("hostmatches"))
async def cmd_host_matches(message: Message):
    user_id = message.from_user.id
    if not await check_host_auth(user_id):
        await message.answer("🚫 Unauthorized.")
        return

    matches = await db.load("matches")
    text = f"⚔️ <b>MATCHES OVERVIEW</b>\n\n"
    count = 0
    for mid, m in matches.items():
        count += 1
        text += f"• <code>{mid}</code>: @{m.get('player1_username')} vs @{m.get('player2_username')} [{m.get('status').upper()}]\n"
        if count >= 10:
            break

    if count == 0:
        text += "No matches recorded yet."
    await message.answer(text, parse_mode="HTML")

@router.message(Command("hostannounce"))
async def cmd_host_announce(message: Message, bot: Bot):
    user_id = message.from_user.id
    if not await check_host_auth(user_id):
        await message.answer("🚫 Unauthorized.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Usage: <code>/hostannounce &lt;tournament_id&gt; &lt;announcement text&gt;</code>", parse_mode="HTML")
        return

    tid = args[1]
    announcement = args[2]

    if not await check_host_auth(user_id, tid):
        await message.answer("🚫 You are not authorized to manage this tournament.")
        return

    tournaments = await db.load("tournaments")
    t = tournaments.get(tid)
    if not t or not t.get("group_chat_id"):
        await message.answer("Tournament or group not found.")
        return

    text = f"📢 <b>HOST ANNOUNCEMENT</b>\n\n🏆 <b>{t['name']}</b>\n\n{announcement}"
    try:
        await bot.send_message(chat_id=t["group_chat_id"], text=text, parse_mode="HTML")
        await message.answer("✅ Announcement broadcasted to tournament group successfully.")
    except Exception as e:
        await message.answer(f"Failed to send to group: {e}")

# HOST CALLBACK DISPATCHER
@router.callback_query(F.data.startswith("host:"))
async def on_host_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    action = parts[1]
    tid = parts[2] if len(parts) > 2 and parts[2] != "none" else None

    if not await check_host_auth(user_id, tid):
        await callback.answer("🚫 You do not have host permission for this tournament.", show_alert=True)
        return

    tournaments = await db.load("tournaments")

    # Action 1: Create Tournament
    if action == "create_tourn":
        new_id = f"t_{uuid.uuid4().hex[:6]}"
        group_id = callback.message.chat.id if callback.message.chat.type in ["group", "supergroup"] else None
        await TournamentService.create_tournament(
            tournament_id=new_id,
            name=f"Host Championship #{new_id[-4:]}",
            description="Host-managed hand cricket tournament",
            mode="host",
            group_chat_id=group_id,
            creator_id=user_id,
            host_id=user_id
        )
        await callback.answer(f"Created Host Tournament {new_id}!", show_alert=True)
        keyboard = get_host_dashboard_keyboard(new_id)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        return

    # Action 2: View Players
    elif action == "view_players":
        if not tid:
            await callback.answer("No tournament selected.", show_alert=True)
            return
        parts = await TournamentService.get_tournament_participants(tid)
        if not parts:
            await callback.answer("No participants registered.", show_alert=True)
            return
        text = f"👥 <b>PLAYERS ({len(parts)}):</b>\n" + "\n".join([f"• @{p['username']} (ID: {p['user_id']})" for p in parts])
        await callback.message.reply(text, parse_mode="HTML")
        await callback.answer()
        return

    # Action 3: Team A / Team B management
    elif action in ["team_a", "team_b", "view_teams"]:
        if not tid:
            await callback.answer("No tournament selected.", show_alert=True)
            return
        teams = await HostTournamentService.get_teams(tid)
        t_a = teams.get("Team A", [])
        t_b = teams.get("Team B", [])
        text = (
            f"📊 <b>TEAM ROSTERS:</b>\n\n"
            f"🔴 <b>TEAM A ({len(t_a)}):</b>\n" + ("\n".join([f"• @{p['username']}" for p in t_a]) or "None") + "\n\n"
            f"🔵 <b>TEAM B ({len(t_b)}):</b>\n" + ("\n".join([f"• @{p['username']}" for p in t_b]) or "None")
        )
        await callback.message.reply(text, parse_mode="HTML")
        await callback.answer()
        return

    # Action 4: Start Match
    elif action == "start_match":
        if not tid:
            await callback.answer("No tournament selected.", show_alert=True)
            return
        parts = await TournamentService.get_tournament_participants(tid)
        if len(parts) < 2:
            await callback.answer("Need at least 2 registered players.", show_alert=True)
            return

        p1 = parts[0]
        p2 = parts[1]
        t = tournaments.get(tid, {})
        group_id = callback.message.chat.id if callback.message.chat.type in ["group", "supergroup"] else t.get("group_chat_id")
        if not group_id:
            await callback.answer("⚠️ No playing group set. Run /setgroup <id> inside your playing group first!", show_alert=True)
            return
        match_id = f"hm_{tid}_{uuid.uuid4().hex[:6]}"

        await GameService.start_new_match(
            match_id=match_id,
            player1_id=p1["user_id"],
            player1_username=p1["username"],
            player2_id=p2["user_id"],
            player2_username=p2["username"],
            group_chat_id=group_id,
            bot=bot,
            tournament_id=tid,
            round_name="Host Match",
            max_balls=36,
            wickets=1
        )
        await callback.answer(f"Match started between @{p1['username']} and @{p2['username']}!", show_alert=True)
        return

    # Action 5: Pause / Resume / End Match
    elif action in ["pause_match", "resume_match", "end_match"]:
        target = None
        for m in GameService.active_matches.values():
            if m.tournament_id == tid:
                target = m
                break

        if not target:
            await callback.answer("No live match currently active in this tournament.", show_alert=True)
            return

        if action == "pause_match":
            target.status = MatchStatus.PAUSED
            await callback.answer("Match paused.", show_alert=True)
        elif action == "resume_match":
            target.status = MatchStatus.IN_PROGRESS
            await callback.answer("Match resumed.", show_alert=True)
        elif action == "end_match":
            target.status = MatchStatus.COMPLETED
            target.result_text = "Ended manually by tournament host."
            GameService.active_matches.pop(target.match_id, None)
            await callback.answer("Match ended.", show_alert=True)

        await GameService.save_match(target)
        return

    # Action 6: View Live Scoreboard
    elif action == "scoreboard":
        target = None
        for m in GameService.active_matches.values():
            if m.tournament_id == tid:
                target = m
                break
        if not target:
            await callback.answer("No ongoing match to display.", show_alert=True)
            return
        sb = ScoreboardFormatter.format_live_scoreboard(target)
        await callback.message.reply(sb, parse_mode="HTML")
        await callback.answer()
        return

    await callback.answer("Host command processed.")
