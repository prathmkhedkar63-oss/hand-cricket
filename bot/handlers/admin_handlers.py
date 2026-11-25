import time
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config.settings import settings
from database.json_manager import db
from bot.services.tournament_service import TournamentService
from bot.services.solo_tournament_service import SoloTournamentService
from bot.services.host_tournament_service import HostTournamentService
from bot.keyboards.admin_keyboards import get_admin_dashboard_keyboard
from bot.middlewares.auth_middleware import is_admin_user, is_super_admin

router = Router(name="admin_handlers")

async def is_admin(user_id: int, username: str = None) -> bool:
    return await is_admin_user(user_id, username)


async def _resolve_target_user(message: Message):
    """Resolve target (user_id, clean_username) from reply or command argument."""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        uname = (u.username or u.first_name or str(u.id)).lstrip("@")
        return u.id, uname

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return None, None

    arg = parts[1].strip().lstrip("@")
    clean_lower = arg.lower()
    users = await db.load("users")
    for uid_str, u_data in users.items():
        if isinstance(u_data, dict) and (u_data.get("username") or "").lstrip("@").lower() == clean_lower:
            return int(uid_str), (u_data.get("username") or arg).lstrip("@")
    if arg.isdigit():
        return int(arg), arg
    return None, arg


@router.message(Command("administrator"))
async def cmd_administrator(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can promote administrators.")
        return

    target_id, target_uname = await _resolve_target_user(message)
    if not target_uname:
        await message.answer("ℹ️ Usage: <code>/administrator @username</code> or reply to a user's message.", parse_mode="HTML")
        return

    clean_lower = target_uname.lower()
    admins = await db.load("admins")
    key = str(target_id) if target_id is not None else f"uname:{clean_lower}"
    admins[key] = {
        "user_id": target_id,
        "username": target_uname,
        "role": "admin",
        "is_active": True,
        "added_at": time.time()
    }
    await db.save("admins", admins)

    await db.append("audit_logs", {
        "actor_id": message.from_user.id,
        "actor": message.from_user.username or str(message.from_user.id),
        "action": "grant_admin",
        "target": target_uname,
        "timestamp": time.time()
    })
    await message.answer(f"✅ @{target_uname} is admin now")


@router.message(Command("revoke_admin"))
async def cmd_revoke_admin(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can revoke admin rights.")
        return

    target_id, target_uname = await _resolve_target_user(message)
    if not target_uname:
        await message.answer("ℹ️ Usage: <code>/revoke_admin @username</code> or reply to a user's message.", parse_mode="HTML")
        return

    clean_lower = target_uname.lower()
    super_uname = settings.SUPER_ADMIN_USERNAME.lstrip("@").lower()
    if (target_id is not None and target_id == settings.SUPER_ADMIN_ID) or clean_lower == super_uname:
        await message.answer("🚫 Cannot revoke Super Admin rights.")
        return

    admins = await db.load("admins")
    removed = False
    if target_id is not None and str(target_id) in admins:
        admins.pop(str(target_id), None)
        removed = True
    if f"uname:{clean_lower}" in admins:
        admins.pop(f"uname:{clean_lower}", None)
        removed = True
    for k in [k for k, v in admins.items() if isinstance(v, dict) and (v.get("username") or "").lstrip("@").lower() == clean_lower]:
        admins.pop(k, None)
        removed = True

    if not removed:
        await message.answer(f"ℹ️ @{target_uname} is not an admin.")
        return

    await db.save("admins", admins)
    await db.append("audit_logs", {
        "actor_id": message.from_user.id,
        "actor": message.from_user.username or str(message.from_user.id),
        "action": "revoke_admin",
        "target": target_uname,
        "timestamp": time.time()
    })
    await message.answer(f"🚫 @{target_uname} admin rights revoked.")


@router.message(Command("messege_push", "message_push"))
async def cmd_messege_push(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can push broadcast messages.")
        return

    parts = (message.text or "").split(maxsplit=1)
    push_text = parts[1].strip() if len(parts) > 1 else ""
    reply_msg = message.reply_to_message

    if not push_text and not reply_msg:
        await message.answer(
            "ℹ️ <b>Usage:</b>\n"
            "• <code>/messege_push Your message here</code>\n"
            "• Or reply to any text/photo/video with <code>/messege_push</code>",
            parse_mode="HTML"
        )
        return

    users = await db.load("users")
    tournaments = await db.load("tournaments")
    matches = await db.load("matches")
    sys_settings = await db.load("settings")

    dm_ids = {
        int(uid) for uid in users.keys()
        if str(uid).lstrip("-").isdigit() and int(uid) > 0
    }
    group_ids = set()
    for src in (tournaments, matches):
        if isinstance(src, dict):
            for rec in src.values():
                if isinstance(rec, dict):
                    gid = rec.get("group_chat_id")
                    if isinstance(gid, int) and gid < 0:
                        group_ids.add(gid)
    for gid in sys_settings.get("known_groups", []):
        if isinstance(gid, int) and gid < 0:
            group_ids.add(gid)
    cur_chat_id = getattr(message.chat, "id", None)
    if isinstance(cur_chat_id, int) and cur_chat_id < 0:
        group_ids.add(cur_chat_id)

    dm_sent = 0
    grp_sent = 0
    failed = 0
    dead_groups = set()

    for chat_id in list(dm_ids) + list(group_ids):
        try:
            if reply_msg and not push_text:
                await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=message.chat.id,
                    message_id=reply_msg.message_id
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📢 <b>JPL CRICKET BOT</b>\n━━━━━━━━━━━━━━━━━━━━\n{push_text}",
                    parse_mode="HTML"
                )
            if chat_id > 0:
                dm_sent += 1
            else:
                grp_sent += 1
        except Exception as e:
            failed += 1
            err = str(e).lower()
            if chat_id < 0 and ("forbidden" in err or "chat not found" in err or "kicked" in err):
                dead_groups.add(chat_id)

    if dead_groups and isinstance(sys_settings.get("known_groups"), list):
        sys_settings["known_groups"] = [g for g in sys_settings["known_groups"] if g not in dead_groups]
        await db.save("settings", sys_settings)

    await db.append("audit_logs", {
        "actor_id": message.from_user.id,
        "actor": message.from_user.username or str(message.from_user.id),
        "action": "messege_push",
        "target": f"dms={dm_sent},groups={grp_sent},failed={failed}",
        "timestamp": time.time()
    })
    await message.answer(
        f"📢 <b>MESSAGE PUSH COMPLETE!</b>\n"
        f"✅ Delivered: <b>{dm_sent + grp_sent}</b> (👤 {dm_sent} DMs • 👥 {grp_sent} Groups)\n"
        f"❌ Failed: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.message(Command("push_fact", "cricket_fun"))
async def cmd_push_fact(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can push cricket facts & jokes.")
        return

    from bot.services.cricket_fun_service import CricketFunService
    if getattr(message.chat, "type", None) in ("group", "supergroup"):
        sys_settings = await db.load("settings")
        known = sys_settings.setdefault("known_groups", [])
        if message.chat.id not in known:
            known.append(message.chat.id)
            await db.save("settings", sys_settings)

    sent, failed = await CricketFunService.post_to_all_groups(bot, skip_active_matches=False)
    if sent == -1:
        await message.answer("⚠️ Could not fetch live cricket headlines from the web right now. Try again shortly.")
        return
    await message.answer(
        f"🏏 <b>LIVE CRICKET HEADLINE & DARK JOKE PUSHED!</b>\n"
        f"✅ Sent to <b>{sent}</b> group(s) | ❌ Failed: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.message(Command("toggle_fun"))
async def cmd_toggle_fun(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can toggle 3h auto-posts.")
        return

    sys_settings = await db.load("settings")
    new_val = not sys_settings.get("fun_autopost_enabled", True)
    sys_settings["fun_autopost_enabled"] = new_val
    await db.save("settings", sys_settings)
    status = "ON (every 3h)" if new_val else "OFF"
    await message.answer(f"🏏 <b>3h Cricket Fact & Dark Joke Auto-Post:</b> <code>{status}</code>", parse_mode="HTML")


@router.message(Command("delete"))
async def cmd_delete_bot_message(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only Bot Admins can delete bot messages.")
        return

    reply_msg = message.reply_to_message
    if not reply_msg:
        await message.answer("ℹ️ Reply to any bot message with <code>/delete</code> to remove it.", parse_mode="HTML")
        return

    if reply_msg.from_user and reply_msg.from_user.id != bot.id:
        await message.answer("⚠️ You can only delete messages sent by the bot.")
        return

    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=reply_msg.message_id)
    except Exception as e:
        await message.answer(f"⚠️ Could not delete message: {e}")
        return

    try:
        await message.delete()
    except Exception:
        pass

@router.message(Command("start_bot"))
async def cmd_start_bot(message: Message):
    if not is_super_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only the Bot Owner can start the bot.")
        return

    sys_settings = await db.load("settings")
    sys_settings["bot_enabled"] = True
    await db.save("settings", sys_settings)

    await db.append("audit_logs", {
        "actor_id": message.from_user.id,
        "actor": message.from_user.username or str(message.from_user.id),
        "action": "start_bot",
        "target": "system",
        "timestamp": time.time()
    })
    await message.answer("✅ <b>BOT STARTED!</b>\n\nThe bot is now active and accepting commands from all players.", parse_mode="HTML")

@router.message(Command("stop_bot"))
async def cmd_stop_bot(message: Message, bot: Bot):
    if not is_super_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Only the Bot Owner can stop the bot.")
        return

    sys_settings = await db.load("settings")
    sys_settings["bot_enabled"] = False
    await db.save("settings", sys_settings)

    await db.append("audit_logs", {
        "actor_id": message.from_user.id,
        "actor": message.from_user.username or str(message.from_user.id),
        "action": "stop_bot",
        "target": "system",
        "timestamp": time.time()
    })

    # Cancel all active turn timers and solo countdowns so nothing runs while stopped
    from bot.services.game_service import GameService
    from game_engine.scoreboard import ScoreboardFormatter
    for mid in list(GameService._turn_timers.keys()):
        GameService.cancel_turn_timer(mid)
    for tid, task in list(SoloTournamentService._running_countdowns.items()):
        if task and not task.done():
            task.cancel()
        SoloTournamentService._running_countdowns.pop(tid, None)

    # Display current scorecards for any ongoing matches even while stopping
    for m in list(GameService.active_matches.values()):
        sb = ScoreboardFormatter.format_live_scoreboard(m)
        if m.group_chat_id:
            try:
                await bot.send_message(chat_id=m.group_chat_id, text=sb, parse_mode="HTML")
            except Exception:
                pass

    await message.answer("🛑 <b>BOT STOPPED!</b>\n\nMaintenance mode enabled. Scorecards for ongoing matches have been displayed. Regular players cannot interact until you run /start_bot.", parse_mode="HTML")

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        await message.answer("🚫 Access denied. Super Admin privileges required.")
        return

    users = await db.load("users")
    tournaments = await db.load("tournaments")
    matches = await db.load("matches")
    hosts = await db.load("hosts")

    text = (
        f"👑 <b>SUPER ADMIN DASHBOARD</b>\n\n"
        f"📊 <b>System Overview:</b>\n"
        f"• Total Players: <b>{len(users)}</b>\n"
        f"• Total Tournaments: <b>{len(tournaments)}</b>\n"
        f"• Total Matches: <b>{len(matches)}</b>\n"
        f"• Authorized Hosts: <b>{len(hosts)}</b>\n\n"
        f"<b>Admin Commands:</b>\n"
        f"• <code>/createtournament [solo|host] [name]</code> - Create tournament in this group\n"
        f"• <code>/setgroup &lt;tournament_id&gt;</code> - Bind a tournament to current group\n"
        f"• <code>/startsolo [tournament_id]</code> - Trigger 120s countdown\n"
        f"• <code>/cancelsolo &lt;tournament_id&gt;</code> - Cancel countdown\n"
        f"• <code>/players</code> - Manage registered players\n"
        f"• <code>/hosts</code> - Manage authorized hosts\n"
        f"• <code>/matches</code> - Monitor matches\n"
        f"• <code>/systemstats</code> - System telemetry\n"
        f"• <code>/start_bot</code> - Enable bot for all users\n"
        f"• <code>/stop_bot</code> - Pause/stop bot for maintenance"
    )
    await message.answer(text, reply_markup=get_admin_dashboard_keyboard(), parse_mode="HTML")

@router.message(Command("createtournament"))
async def cmd_create_tournament(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    args = message.text.split(maxsplit=2)
    mode = "solo"
    if len(args) > 1 and args[1].lower() in ["solo", "host"]:
        mode = args[1].lower()
    name = args[2] if len(args) > 2 else f"Hand Cricket Cup ({mode.upper()})"

    t_id = f"trn_{uuid.uuid4().hex[:6]}"
    is_group = message.chat.type in ["group", "supergroup"]
    group_id = message.chat.id if is_group else None

    t = await TournamentService.create_tournament(
        tournament_id=t_id,
        name=name,
        description=f"Official {mode} hand cricket championship",
        mode=mode,
        group_chat_id=group_id,
        creator_id=message.from_user.id
    )

    arena_note = (
        f"🏟️ <b>Playing Group:</b> This group (<code>{message.chat.id}</code>)\n"
        if is_group else
        f"ℹ️ <i>To link this tournament to a specific group, go to that group and type:</i>\n<code>/setgroup {t_id}</code>\n"
    )

    await message.answer(
        f"✅ <b>Tournament Created!</b>\n\n"
        f"🏆 Name: <b>{t['name']}</b>\n"
        f"🆔 ID: <code>{t_id}</code>\n"
        f"⚙️ Mode: <b>{mode.upper()}</b>\n"
        f"{arena_note}\n"
        f"Players can join with <code>/tournaments</code> or register buttons in the group.",
        parse_mode="HTML"
    )

@router.message(Command("setgroup"))
async def cmd_set_group(message: Message):
    """
    Dynamically binds a tournament to the current Telegram group!
    Allows playing tournaments in any group on demand.
    """
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ This command must be used inside the Telegram group where you want to play.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: <code>/setgroup &lt;tournament_id&gt;</code>", parse_mode="HTML")
        return

    t_id = args[1]
    tournaments = await db.load("tournaments")
    t = tournaments.get(t_id)
    if not t:
        await message.answer("❌ Tournament not found.")
        return

    # Check permission (Super Admin or authorized host)
    user_id = message.from_user.id
    is_auth_host = await HostTournamentService.is_host_authorized(user_id, t_id)
    if not await is_admin(user_id, message.from_user.username) and not is_auth_host:
        await message.answer("🚫 You are not authorized to configure this tournament.")
        return

    t["group_chat_id"] = message.chat.id
    await db.save("tournaments", tournaments)

    await message.answer(
        f"🏟️ <b>ARENA SET SUCCESSFULLY!</b>\n\n"
        f"🏆 Tournament: <b>{t['name']}</b> (<code>{t_id}</code>)\n"
        f"📍 Group: <b>{message.chat.title or message.chat.id}</b>\n\n"
        f"All batting deliveries, scoreboards, and announcements for this tournament will now take place in this group!",
        parse_mode="HTML"
    )

@router.message(Command("startsolo"))
async def cmd_start_solo(message: Message, bot: Bot):
    """
    Triggers the 120-second automated solo tournament countdown.
    Automatically detects the tournament for this group if none specified.
    """
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    tournaments = await db.load("tournaments")
    args = message.text.split()
    t_id = None

    if len(args) >= 2:
        t_id = args[1]
    else:
        # If in a group, look for active solo tournament for this group
        if message.chat.type in ["group", "supergroup"]:
            for tid, t in tournaments.items():
                if t.get("mode") == "solo" and t.get("status") in ["registration", "countdown"] and t.get("group_chat_id") == message.chat.id:
                    t_id = tid
                    break

    if not t_id:
        await message.answer("Usage: <code>/startsolo &lt;tournament_id&gt;</code> (or run in a group that has an active solo tournament)", parse_mode="HTML")
        return

    t = tournaments.get(t_id)
    if not t:
        await message.answer("Tournament not found.")
        return

    # If run in group and tournament had no group set, bind it now!
    if message.chat.type in ["group", "supergroup"]:
        t["group_chat_id"] = message.chat.id
        await db.save("tournaments", tournaments)

    group_id = t.get("group_chat_id", message.chat.id)
    success, msg = await SoloTournamentService.start_countdown(t_id, bot, group_id)
    await message.answer(msg)

@router.message(Command("cancelsolo"))
async def cmd_cancel_solo(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    tournaments = await db.load("tournaments")
    args = message.text.split()
    t_id = None
    if len(args) >= 2:
        t_id = args[1]
    elif message.chat.type in ["group", "supergroup"]:
        for tid, t in tournaments.items():
            if t.get("mode") == "solo" and t.get("status") == "countdown" and t.get("group_chat_id") == message.chat.id:
                t_id = tid
                break

    if not t_id:
        await message.answer("Usage: <code>/cancelsolo &lt;tournament_id&gt;</code>", parse_mode="HTML")
        return

    success, msg = await SoloTournamentService.cancel_countdown(t_id, bot, message.from_user.id)
    await message.answer(msg)

@router.message(Command("players"))
async def cmd_admin_players(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    users = await db.load("users")
    stats = await db.load("statistics")
    text = f"👥 <b>REGISTERED PLAYERS ({len(users)})</b>\n\n"
    for idx, (uid, u) in enumerate(list(users.items())[:15], 1):
        s = stats.get(uid, {})
        status = "🚫 Banned" if u.get("is_banned") else "✅ Active"
        text += f"{idx}. @{u.get('username')} (ID: <code>{uid}</code>) - {s.get('matches_won', 0)}W/{s.get('matches_played', 0)}M [{status}]\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("hosts"))
async def cmd_admin_hosts(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    hosts = await db.load("hosts")
    text = f"🛡️ <b>AUTHORIZED HOSTS ({len(hosts)})</b>\n\n"
    if not hosts:
        text += "No hosts currently registered."
    else:
        for idx, (uid, h) in enumerate(hosts.items(), 1):
            status = "Authorized" if h.get("is_active", True) else "Revoked"
            text += f"{idx}. @{h.get('username')} (ID: <code>{uid}</code>) - [{status}]\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("matches"))
async def cmd_admin_matches(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    matches = await db.load("matches")
    text = f"⚔️ <b>RECENT MATCHES ({len(matches)})</b>\n\n"
    if not matches:
        text += "No matches recorded yet."
    else:
        for idx, (mid, m) in enumerate(list(matches.items())[-10:], 1):
            text += f"{idx}. <code>{mid}</code>: @{m.get('player1_username')} vs @{m.get('player2_username')} [{m.get('status').upper()}]\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("systemstats"))
async def cmd_systemstats(message: Message):
    if not await is_admin(message.from_user.id, message.from_user.username):
        return

    users = await db.load("users")
    tournaments = await db.load("tournaments")
    matches = await db.load("matches")
    balls = await db.load("ball_history")

    text = (
        f"📈 <b>SYSTEM TELEMETRY & STATS</b>\n\n"
        f"👤 Registered Players: <b>{len(users)}</b>\n"
        f"🏆 Tournaments: <b>{len(tournaments)}</b>\n"
        f"⚔️ Matches Recorded: <b>{len(matches)}</b>\n"
        f"🏏 Total Deliveries Bowled: <b>{len(balls)}</b>\n"
        f"💾 Storage Engine: Atomic JSON with File Locking\n"
        f"🛡️ Status: Operational & Healthy"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin:"))
async def on_admin_callback(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    action = callback.data.split(":")[1]
    if action == "backup":
        path = await db.create_backup("admin_manual")
        await callback.answer(f"Backup created: {path.split('/')[-1]}", show_alert=True)
    elif action == "systemstats":
        users = await db.load("users")
        matches = await db.load("matches")
        await callback.answer(f"Players: {len(users)} | Matches: {len(matches)}", show_alert=True)
    elif action == "players":
        users = await db.load("users")
        await callback.message.reply(f"Total registered players: {len(users)}. Use /players to list.", parse_mode="HTML")
        await callback.answer()
    elif action == "hosts":
        hosts = await db.load("hosts")
        await callback.message.reply(f"Total authorized hosts: {len(hosts)}. Use /hosts to list.", parse_mode="HTML")
        await callback.answer()
    elif action == "matches":
        matches = await db.load("matches")
        await callback.message.reply(f"Total matches: {len(matches)}. Use /matches to list.", parse_mode="HTML")
        await callback.answer()
    else:
        await callback.answer(f"Admin action: {action}")
