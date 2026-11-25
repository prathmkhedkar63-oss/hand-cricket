import logging
from pathlib import Path
from typing import Dict, Optional
from aiogram import Bot
from aiogram.types import Message, FSInputFile

logger = logging.getLogger("media_service")

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "images"

class MediaService:
    """
    Sends pre-generated lightweight JPEG banners and caches Telegram file_ids
    so every subsequent send uses 0 upload bandwidth.
    """
    _file_id_cache: Dict[str, str] = {}

    IMAGES: Dict[str, Path] = {
        "welcome": ASSETS_DIR / "welcome.jpg",
        "match_start": ASSETS_DIR / "match_start.jpg",
        "six": ASSETS_DIR / "six.jpg",
        "wicket": ASSETS_DIR / "wicket.jpg",
        "champion": ASSETS_DIR / "champion.jpg",
    }

    @classmethod
    async def send_with_image(
        cls,
        bot: Bot,
        chat_id: int,
        image_key: str,
        caption: str,
        reply_markup=None
    ) -> Optional[Message]:
        """
        Sends an image + caption to a chat using cached file_id when available.
        Falls back cleanly to plain text if image is missing or send_photo fails.
        """
        img_path = cls.IMAGES.get(image_key)
        cached_id = cls._file_id_cache.get(image_key)

        if cached_id or (img_path and img_path.exists()):
            photo = cached_id or FSInputFile(str(img_path))
            try:
                msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption[:1024],
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                # Cache Telegram's file_id after first upload for zero-bandwidth reuse
                if not cached_id and getattr(msg, "photo", None):
                    cls._file_id_cache[image_key] = msg.photo[-1].file_id
                return msg
            except Exception as e:
                logger.debug(f"send_photo fallback to text ({image_key}): {e}")

        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
