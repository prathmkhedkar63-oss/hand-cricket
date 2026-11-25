import time
import logging
from typing import Optional, List, Dict, Any
from aiogram import Bot
from database.json_manager import db

logger = logging.getLogger("notification_service")

class NotificationService:
    @staticmethod
    async def log_and_send(
        bot: Bot,
        chat_id: int,
        text: str,
        category: str = "general",
        user_id: Optional[int] = None
    ) -> bool:
        now = time.time()
        record = {
            "chat_id": chat_id,
            "user_id": user_id,
            "category": category,
            "text": text,
            "timestamp": now,
            "delivered": False
        }
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            record["delivered"] = True
            await db.append("notifications", record)
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification to {chat_id}: {e}")
            await db.append("notifications", record)
            return False

    @staticmethod
    async def broadcast_tournament_announcement(bot: Bot, group_chat_id: int, tournament_name: str, message: str):
        text = (
            f"📢 <b>TOURNAMENT ANNOUNCEMENT</b>\n\n"
            f"🏆 Tournament: <b>{tournament_name}</b>\n\n"
            f"{message}"
        )
        await NotificationService.log_and_send(bot, group_chat_id, text, category="announcement")
