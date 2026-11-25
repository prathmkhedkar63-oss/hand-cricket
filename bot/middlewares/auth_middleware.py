import time
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, Message, CallbackQuery
from bot.services.stats_service import StatsService
from config.settings import settings
from database.json_manager import db

async def is_admin_user(user_id: int, username: Optional[str] = None) -> bool:
    """
    Checks if the user is a Super Admin via numeric ID, configured username (@prathamesh63), or admins.json.
    """
    if user_id == settings.SUPER_ADMIN_ID:
        return True

    clean_uname = (username or "").lstrip("@").lower()
    if clean_uname and clean_uname == settings.SUPER_ADMIN_USERNAME.lstrip("@").lower():
        # Persist numeric ID in admins.json for permanent binding
        admins = await db.load("admins")
        if str(user_id) not in admins:
            admins[str(user_id)] = {
                "user_id": user_id,
                "username": clean_uname,
                "role": "superadmin",
                "is_active": True,
                "added_at": time.time()
            }
            await db.save("admins", admins)
        return True

    admins = await db.load("admins")
    admin_rec = admins.get(str(user_id))
    if admin_rec is not None:
        return bool(admin_rec.get("is_active", True))

    if clean_uname and f"uname:{clean_uname}" in admins:
        pending = admins.pop(f"uname:{clean_uname}")
        if pending.get("is_active", True):
            admins[str(user_id)] = {
                "user_id": user_id,
                "username": clean_uname,
                "role": pending.get("role", "admin"),
                "is_active": True,
                "added_at": pending.get("added_at", time.time())
            }
            await db.save("admins", admins)
            return True
    return False

class AuthMiddleware(BaseMiddleware):
    """
    Ensures every user interacting with the bot is registered in users.json,
    updates their username if changed, checks for banned status, and enforces
    admin-controlled bot start/stop state.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        if user:
            user_info = await StatsService.get_or_create_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name or ""
            )
            if user_info.get("is_banned"):
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 Your account has been banned from this bot.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("🚫 Your account has been banned from this bot.")
                return

            # Enforce bot_enabled state (admins are always allowed so they can run /start_bot)
            sys_settings = await db.load("settings")
            if not sys_settings.get("bot_enabled", True):
                if not await is_admin_user(user.id, user.username):
                    if isinstance(event, CallbackQuery):
                        await event.answer("🛑 The bot is currently stopped by an administrator.", show_alert=True)
                    elif isinstance(event, Message):
                        is_dm = getattr(event.chat, "type", None) == "private"
                        is_cmd = bool(event.text and event.text.strip().startswith("/"))
                        if is_dm or is_cmd:
                            await event.answer("🛑 The bot is currently stopped by an administrator.")
                    return

            data["user_info"] = user_info

        return await handler(event, data)
