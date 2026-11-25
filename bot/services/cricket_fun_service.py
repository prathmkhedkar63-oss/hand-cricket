import asyncio
import html
import logging
import random
import re
import xml.etree.ElementTree as ET
from collections import deque
from typing import List, Optional, Tuple
import httpx
from aiogram import Bot

from database.json_manager import db
from bot.services.game_service import GameService

logger = logging.getLogger("cricket_fun")

RSS_FEEDS: List[str] = [
    "https://news.google.com/rss/search?q=cricket&hl=en-IN&gl=IN&ceid=IN:en",
    "https://feeds.bbci.co.uk/sport/cricket/rss.xml",
    "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
]

KEYWORD_DARK_ROASTS: List[Tuple[Tuple[str, ...], List[str]]] = [
    (
        ("rcb", "bengaluru", "kohli"),
        [
            "RCB fans reading this headline like it's finally their year—spoiler: the trophy cabinet is still collecting dust.",
            "Even after reading this, RCB's bowling attack is still the biggest charity foundation in cricket.",
        ],
    ),
    (
        ("duck", "bowled", "out", "wicket", "collapse", "all out"),
        [
            "Batsmen collapsing faster than my willpower on a Monday morning—pure Hand Cricket Ball-1 energy.",
            "At this point, the dressing room needs a revolving door instead of a staircase.",
        ],
    ),
    (
        ("injured", "injury", "ruled out", "fitness", "dropped"),
        [
            "Selectors dropping players faster than Hand Cricket captains swap an AFK bowler after 3 warnings.",
            "Half the squad spends more time in rehab than at the crease—medical staff deserves Man of the Series.",
        ],
    ),
    (
        ("ipl", "auction", "crore", "mega", "franchise", "retained"),
        [
            "Paying crores for a player just to watch them score 4(7) and smile in post-match interviews.",
            "Franchise owners burning billions while we play Hand Cricket for free and still get more drama.",
        ],
    ),
    (
        ("final", "semi", "world cup", "trophy", "icc", "champions"),
        [
            "Nothing bonds cricket fans faster than watching their team bottle a knockout match they had 90% won.",
            "Every ICC knockout is just 4 hours of false hope followed by staring at the ceiling in silence.",
        ],
    ),
    (
        ("century", "hundred", "ton", "six", "record", "win"),
        [
            "Meanwhile, my only cricket record is getting bowled on 0 after typing 6 like an optimist.",
            "Bowlers watched that happen and immediately started updating their LinkedIn profiles.",
        ],
    ),
]

GENERAL_DARK_ROASTS: List[str] = [
    "Cricket headlines never disappoint—10% sport, 90% collective fan trauma.",
    "Meanwhile, in Hand Cricket, one wrong number still ends your whole career in 0.2 seconds.",
    "Selectors saw this headline and still found a way to ruin someone's confidence.",
    "Fans celebrating today like they won't be crying over a middle-order collapse next week.",
    "Proof that cricket is just emotional damage disguised as a gentleman's game.",
]


class CricketFunService:
    """Fetches live cricket headlines/news from the web, adds a dark cricket joke, and posts to groups."""

    _recent_headlines: deque = deque(maxlen=30)
    AUTO_INTERVAL_SECONDS: int = 3 * 3600  # Every 3 hours

    @classmethod
    def _parse_rss_titles(cls, xml_text: str) -> List[str]:
        titles: List[str] = []
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item/title"):
                if item.text:
                    clean = html.unescape(re.sub(r"\s+", " ", item.text)).strip()
                    # Strip trailing " - Source Name" from Google News headlines
                    clean = re.sub(r"\s+-\s+[^-]+$", "", clean).strip()
                    if len(clean) > 18:
                        titles.append(clean)
        except Exception as e:
            logger.debug(f"RSS parse error: {e}")
        return titles

    @classmethod
    async def fetch_web_headlines(cls) -> List[str]:
        feeds = list(RSS_FEEDS)
        random.shuffle(feeds)
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            for url in feeds:
                try:
                    resp = await client.get(url, headers={"User-Agent": "JPLCricketBot/1.0"})
                    if resp.status_code == 200 and resp.text:
                        titles = cls._parse_rss_titles(resp.text)
                        if titles:
                            return titles
                except Exception as e:
                    logger.debug(f"Feed fetch failed ({url}): {e}")
        return []

    @classmethod
    def make_dark_joke_for_headline(cls, headline: str) -> str:
        low = headline.lower()
        for keywords, roasts in KEYWORD_DARK_ROASTS:
            if any(kw in low for kw in keywords):
                return random.choice(roasts)
        return random.choice(GENERAL_DARK_ROASTS)

    @classmethod
    async def get_live_headline_and_joke(cls) -> Tuple[Optional[str], Optional[str]]:
        titles = await cls.fetch_web_headlines()
        if not titles:
            return None, None

        fresh = [t for t in titles[:20] if t not in cls._recent_headlines]
        chosen = random.choice(fresh or titles[:20])
        cls._recent_headlines.append(chosen)
        return chosen, cls.make_dark_joke_for_headline(chosen)

    @staticmethod
    def format_fun_card(headline: str, joke: str) -> str:
        return (
            "🏏 <b>JPL CRICKET BOT • LIVE CRICKET BUZZ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 <b>Headline:</b> <i>{html.escape(headline)}</i>\n\n"
            f"💀 <b>Joke:</b> <i>{html.escape(joke)}</i>"
        )

    @classmethod
    async def post_to_all_groups(cls, bot: Bot, skip_active_matches: bool = True) -> Tuple[int, int]:
        headline, joke = await cls.get_live_headline_and_joke()
        if not headline or not joke:
            return -1, 0

        sys_settings = await db.load("settings")
        tournaments = await db.load("tournaments")
        matches = await db.load("matches")

        group_ids = set()
        for gid in sys_settings.get("known_groups", []):
            if isinstance(gid, int) and gid < 0:
                group_ids.add(gid)
        for src in (tournaments, matches):
            if isinstance(src, dict):
                for rec in src.values():
                    if isinstance(rec, dict):
                        gid = rec.get("group_chat_id")
                        if isinstance(gid, int) and gid < 0:
                            group_ids.add(gid)

        if not group_ids:
            return 0, 0

        busy_groups = {
            m.group_chat_id for m in GameService.active_matches.values() if m.group_chat_id
        } if skip_active_matches else set()

        text = cls.format_fun_card(headline, joke)
        sent = 0
        failed = 0
        dead_groups = set()
        for gid in group_ids:
            if gid in busy_groups:
                continue
            try:
                await bot.send_message(chat_id=gid, text=text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                err = str(e).lower()
                if "forbidden" in err or "chat not found" in err or "kicked" in err:
                    dead_groups.add(gid)

        if dead_groups and isinstance(sys_settings.get("known_groups"), list):
            sys_settings["known_groups"] = [g for g in sys_settings["known_groups"] if g not in dead_groups]
            await db.save("settings", sys_settings)

        return sent, failed

    @classmethod
    async def auto_poster_worker(cls, bot: Bot):
        """Posts a live web cricket headline + dark joke every 3 hours to idle groups."""
        while True:
            try:
                await asyncio.sleep(cls.AUTO_INTERVAL_SECONDS)
                sys_settings = await db.load("settings")
                if not sys_settings.get("bot_enabled", True):
                    continue
                if not sys_settings.get("fun_autopost_enabled", True):
                    continue
                await cls.post_to_all_groups(bot, skip_active_matches=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CricketFun auto_poster error: {e}")
