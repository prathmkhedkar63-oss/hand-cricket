import logging
import random
from pathlib import Path
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import Message, FSInputFile, BufferedInputFile

logger = logging.getLogger("media_service")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT_DIR / "assets" / "images"
VIDEOS_DIR = ROOT_DIR / "assets" / "videos"

class MediaService:
    """
    Sends pre-generated lightweight JPEG banners and MP4 clips, caching Telegram
    file_ids so every subsequent send uses 0 upload bandwidth.
    """
    _file_id_cache: Dict[str, str] = {}
    _video_file_id_cache: Dict[str, str] = {}

    IMAGES: Dict[str, Path] = {
        "welcome": ASSETS_DIR / "welcome.jpg",
        "match_start": ASSETS_DIR / "match_start.jpg",
        "six": ASSETS_DIR / "six.jpg",
        "wicket": ASSETS_DIR / "wicket.jpg",
        "champion": ASSETS_DIR / "champion.jpg",
    }

    VIDEOS: Dict[str, List[str]] = {
        "on_ready": ["on ready.mp4"],
        "dot": ["dot.mp4", "0 ro 1.mp4"],
        "1": ["0 ro 1.mp4"],
        "2": ["2.mp4"],
        "3": ["3.mp4"],
        "4": ["4.mp4", "4(1).mp4"],
        "6": ["6.mp4", "6(1).mp4"],
        "out": ["out.mp4", "out(1).mp4"],
        "50": ["50.mp4"],
        "100": ["100.mp4"],
        "match_over": ["match over.mp4"],
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

    @classmethod
    async def send_generated_image(
        cls,
        bot: Bot,
        chat_id: int,
        image_bytes: bytes,
        filename: str,
        caption: str,
        reply_markup=None
    ) -> Optional[Message]:
        """
        Delivers an in-memory generated JPEG directly to Telegram without storing it
        on disk or in the database. Falls back to plain text if send_photo fails.
        """
        try:
            photo = BufferedInputFile(image_bytes, filename=filename)
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption[:1024],
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.debug(f"send_generated_image fallback to text ({filename}): {e}")
            return await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

    @classmethod
    def _resolve_video_path(cls, filename: str) -> Optional[Path]:
        for base in (VIDEOS_DIR, ROOT_DIR):
            candidate = base / filename
            if candidate.exists():
                return candidate
        return None

    @classmethod
    async def send_video_or_animation(
        cls,
        bot: Bot,
        chat_id: int,
        video_key: str,
        caption: str,
        reply_markup=None
    ) -> Optional[Message]:
        """
        Sends an MP4 clip (randomly choosing among variants like 6.mp4 / 6(1).mp4)
        via send_animation (plays inline like a GIF) with send_video & text fallback.
        Caches Telegram file_id per filename for zero-bandwidth reuse.
        """
        candidates = cls.VIDEOS.get(video_key, [])
        available = [(name, cls._resolve_video_path(name)) for name in candidates]
        available = [(name, path) for name, path in available if cls._video_file_id_cache.get(name) or path]

        if available:
            filename, path = random.choice(available)
            cached_id = cls._video_file_id_cache.get(filename)
            media = cached_id or FSInputFile(str(path))
            for sender in ("send_animation", "send_video"):
                try:
                    fn = getattr(bot, sender)
                    kwargs = {
                        "chat_id": chat_id,
                        "caption": caption[:1024],
                        "reply_markup": reply_markup,
                        "parse_mode": "HTML",
                    }
                    if sender == "send_animation":
                        kwargs["animation"] = media
                    else:
                        kwargs["video"] = media
                    msg = await fn(**kwargs)
                    if not cached_id:
                        anim = getattr(msg, "animation", None)
                        vid = getattr(msg, "video", None)
                        fid = getattr(anim, "file_id", None) or getattr(vid, "file_id", None)
                        if fid:
                            cls._video_file_id_cache[filename] = fid
                    return msg
                except Exception as e:
                    logger.debug(f"{sender} fallback ({filename}): {e}")

        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
