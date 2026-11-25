import time
from collections import deque
from typing import Callable, Dict, Any, Awaitable, Deque
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, CallbackQuery, Message

class RateLimitMiddleware(BaseMiddleware):
    """
    Lightweight, memory-bounded anti-spam & flood protection middleware.
    - Enforces per-user cooldown (0.4s)
    - Detects rapid flooding (>8 actions in 5s) and applies a 10s temporary mute
    - Automatically prunes stale entries to keep RAM usage flat
    """
    def __init__(self, limit_seconds: float = 0.4, flood_count: int = 8, flood_window: float = 5.0, mute_seconds: float = 10.0):
        self.limit_seconds = limit_seconds
        self.flood_count = flood_count
        self.flood_window = flood_window
        self.mute_seconds = mute_seconds
        self.user_last_action: Dict[int, float] = {}
        self.user_timestamps: Dict[int, Deque[float]] = {}
        self.muted_until: Dict[int, float] = {}
        self.mute_notified: Dict[int, float] = {}

    def _prune_stale(self, now: float):
        if len(self.user_last_action) > 500:
            cutoff = now - 60.0
            stale = [uid for uid, ts in self.user_last_action.items() if ts < cutoff]
            for uid in stale:
                self.user_last_action.pop(uid, None)
                self.user_timestamps.pop(uid, None)
                self.muted_until.pop(uid, None)
                self.mute_notified.pop(uid, None)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        if user:
            now = time.time()
            uid = user.id
            self._prune_stale(now)

            # Exempt single-digit gameplay moves (0-6) from flood mute (keep 0.25s debounce)
            is_gameplay_num = (
                isinstance(event, Message)
                and event.text is not None
                and event.text.strip() in {"0", "1", "2", "3", "4", "5", "6"}
            )
            min_gap = 0.25 if is_gameplay_num else self.limit_seconds

            # 1. Check active flood mute
            if not is_gameplay_num:
                mute_end = self.muted_until.get(uid, 0.0)
                if now < mute_end:
                    if isinstance(event, CallbackQuery):
                        await event.answer("⏳ Slow down! Too many requests.", show_alert=False)
                    elif isinstance(event, Message) and now - self.mute_notified.get(uid, 0.0) > self.mute_seconds:
                        self.mute_notified[uid] = now
                        await event.reply("⏳ Anti-spam active: please wait a few seconds.")
                    return

            # 2. Check short cooldown
            last_time = self.user_last_action.get(uid, 0.0)
            if now - last_time < min_gap:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ Please slow down!", show_alert=False)
                return
            self.user_last_action[uid] = now

            # 3. Sliding-window flood detection (non-gameplay spam)
            if not is_gameplay_num:
                window = self.user_timestamps.setdefault(uid, deque(maxlen=self.flood_count + 1))
                window.append(now)
                if len(window) >= self.flood_count and (now - window[0]) < self.flood_window:
                    self.muted_until[uid] = now + self.mute_seconds
                    window.clear()
                    if isinstance(event, CallbackQuery):
                        await event.answer("🚫 Spam detected! Cooldown for 10s.", show_alert=True)
                    elif isinstance(event, Message):
                        self.mute_notified[uid] = now
                        await event.reply("🚫 Spam detected! Please wait 10 seconds before sending more commands.")
                    return

        return await handler(event, data)
