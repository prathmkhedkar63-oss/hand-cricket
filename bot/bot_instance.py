import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from config.settings import settings
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.middlewares.rate_limit_middleware import RateLimitMiddleware

logger = logging.getLogger("bot_instance")

def create_bot() -> Bot:
    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    # Middlewares (RateLimit first to drop spam before auth/DB checks)
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.update.middleware(AuthMiddleware())
    return dp

async def setup_bot_commands(bot: Bot):
    """
    Registers native Telegram command lists for the bot menu popup in both private chats and groups.
    """
    # Private chat commands
    private_commands = [
        BotCommand(command="start", description="Register & main menu"),
        BotCommand(command="help", description="Show full instructions & commands"),
        BotCommand(command="profile", description="View your player profile"),
        BotCommand(command="stats", description="View cricket career statistics"),
        BotCommand(command="history", description="Recent match history"),
        BotCommand(command="leaderboard", description="Global rankings & top players"),
        BotCommand(command="tournaments", description="Browse tournaments"),
        BotCommand(command="mytournaments", description="Your joined tournaments"),
        BotCommand(command="challenge_bot", description="Play 1v1 against the Smart Bot"),
        BotCommand(command="rules", description="Game & tournament rules"),
        BotCommand(command="about", description="About this bot & creator"),
        BotCommand(command="host", description="Open Host Control Panel"),
        BotCommand(command="admin", description="Open Admin Dashboard"),
        BotCommand(command="start_bot", description="Admin: Enable bot"),
        BotCommand(command="stop_bot", description="Admin: Stop bot for maintenance"),
        BotCommand(command="administrator", description="Admin: Grant bot admin rights"),
        BotCommand(command="revoke_admin", description="Admin: Revoke bot admin rights"),
        BotCommand(command="messege_push", description="Admin: Broadcast message to DMs & groups"),
        BotCommand(command="push_fact", description="Admin: Post cricket fact & dark joke to groups"),
        BotCommand(command="toggle_fun", description="Admin: Toggle 3h fact/joke auto-post"),
    ]

    # Group chat commands
    group_commands = [
        BotCommand(command="start", description="Show tournament & play menu"),
        BotCommand(command="start_solo", description="Start automated 120s solo tournament"),
        BotCommand(command="start_tournament", description="Create host-managed tournament"),
        BotCommand(command="add_a", description="Add player(s) to Team A (max 11)"),
        BotCommand(command="add_b", description="Add player(s) to Team B (max 11)"),
        BotCommand(command="remove_a", description="Remove player(s) from Team A"),
        BotCommand(command="remove_b", description="Remove player(s) from Team B"),
        BotCommand(command="swap", description="Substitute player by roster number"),
        BotCommand(command="cap_a", description="Set Captain for Team A"),
        BotCommand(command="cap_b", description="Set Captain for Team B"),
        BotCommand(command="overs", description="Set match overs limit"),
        BotCommand(command="teams", description="View team rosters & captains"),
        BotCommand(command="toss", description="Coin toss & Bat/Bowl choice"),
        BotCommand(command="score", description="View current live match scorecard"),
        BotCommand(command="challenge_bot", description="Play 1v1 against the Smart Bot"),
        BotCommand(command="start_match", description="Start Team A vs Team B match"),
        BotCommand(command="appoint_bowler", description="Host/Captain: appoint new bowler"),
        BotCommand(command="appoint_batsman", description="Host/Captain: appoint new batsman"),
        BotCommand(command="cancel", description="Group Admin: cancel ongoing tournament/match"),
        BotCommand(command="tournaments", description="Tournaments in this group"),
        BotCommand(command="stats", description="View your statistics"),
        BotCommand(command="leaderboard", description="View global rankings"),
        BotCommand(command="rules", description="Game rules"),
        BotCommand(command="about", description="About this bot & creator"),
        BotCommand(command="help", description="Show complete command guide"),
        BotCommand(command="start_bot", description="Admin: Enable bot"),
        BotCommand(command="stop_bot", description="Admin: Stop bot"),
        BotCommand(command="administrator", description="Admin: Make user bot admin"),
        BotCommand(command="revoke_admin", description="Admin: Revoke bot admin"),
        BotCommand(command="messege_push", description="Admin: Broadcast message to DMs & groups"),
        BotCommand(command="push_fact", description="Admin: Post cricket fact & dark joke to groups"),
        BotCommand(command="toggle_fun", description="Admin: Toggle 3h fact/joke auto-post"),
    ]

    # Default fallback commands
    default_commands = [
        BotCommand(command="start", description="Register or check status"),
        BotCommand(command="help", description="Show full command list"),
        BotCommand(command="tournaments", description="View tournaments"),
        BotCommand(command="profile", description="Your profile"),
        BotCommand(command="stats", description="Career stats"),
        BotCommand(command="leaderboard", description="Rankings"),
        BotCommand(command="rules", description="Game rules"),
        BotCommand(command="host", description="Host control panel"),
        BotCommand(command="admin", description="Admin control panel"),
    ]

    try:
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        logger.info("Telegram native command lists successfully registered.")
    except Exception as e:
        logger.warning(f"Could not register Telegram bot commands: {e}")
