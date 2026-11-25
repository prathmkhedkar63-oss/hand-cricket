import sys
from pathlib import Path

# Add project root directory to sys.path so modules like config, database, bot can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import logging
import os
import httpx
import uvicorn
from aiogram import Bot
from config.settings import settings
from database.json_manager import db
from bot import setup_bot
from bot.services.solo_tournament_service import SoloTournamentService
from backend.main import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main_runner")

async def run_fastapi():
    config = uvicorn.Config(app=app, host=settings.API_HOST, port=settings.API_PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"Starting FastAPI Server on {settings.API_HOST}:{settings.API_PORT}")
    await server.serve()

async def run_bot(bot: Bot, dp):
    logger.info("Initializing Hand Cricket Bot...")
    # Register native Telegram command list popups
    from bot.bot_instance import setup_bot_commands
    await setup_bot_commands(bot)

    # Recover any solo tournament countdowns interrupted by restart
    await SoloTournamentService.recover_active_countdowns(bot)
    logger.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)

async def keep_alive_worker():
    """
    Periodically pings the public /health endpoint (if KEEP_ALIVE_URL, RENDER_EXTERNAL_URL,
    or SPACE_HOST is set) so free-tier cloud containers stay awake.
    """
    url = os.environ.get("KEEP_ALIVE_URL")
    if not url:
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        space_host = os.environ.get("SPACE_HOST")
        if render_url:
            url = f"{render_url.rstrip('/')}/health"
        elif space_host:
            url = f"https://{space_host}/health"
    if not url:
        return

    await asyncio.sleep(30)
    logger.info(f"Keep-alive pinger enabled for: {url}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                await client.get(url)
            except Exception as e:
                logger.debug(f"Keep-alive ping failed: {e}")
            await asyncio.sleep(600)  # Every 10 minutes (keeps Render free tier awake)

async def main():
    # 1. Initialize DB tables & default admin/settings
    db.initialize_tables()
    logger.info("Database tables initialized.")

    # 2. Setup Bot
    bot, dp = setup_bot()

    # 3. Concurrently run FastAPI Admin API, Aiogram Bot, and Keep-Alive Pinger
    await asyncio.gather(
        run_fastapi(),
        run_bot(bot, dp),
        keep_alive_worker()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot & API service stopped.")
