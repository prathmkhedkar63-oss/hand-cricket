from bot.bot_instance import create_bot, create_dispatcher
from bot.handlers.player_handlers import router as player_router
from bot.handlers.game_handlers import router as game_router
from bot.handlers.host_handlers import router as host_router
from bot.handlers.admin_handlers import router as admin_router

def setup_bot():
    bot = create_bot()
    dp = create_dispatcher()
    dp.include_router(player_router)
    dp.include_router(game_router)
    dp.include_router(host_router)
    dp.include_router(admin_router)
    return bot, dp
