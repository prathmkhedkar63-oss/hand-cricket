import pytest
from game_engine.engine import GameEngine
from game_engine.models import MatchStatus

def test_security_unauthorized_bowler():
    match = GameEngine.create_match("sec_m1", 101, "bat1", 202, "bowl1")
    
    # Random unauthorized user attempts to bowl
    success, msg = GameEngine.record_bowler_choice(match, bowler_id=999, number=4)
    assert not success
    assert "not the designated bowler" in msg
    assert match.pending_bowler_number is None

def test_security_unauthorized_batsman():
    match = GameEngine.create_match("sec_m2", 101, "bat1", 202, "bowl1")
    GameEngine.record_bowler_choice(match, bowler_id=202, number=3)
    
    # Random unauthorized user attempts to bat
    success, msg, ball = GameEngine.record_batsman_choice(match, batsman_id=999, number=3)
    assert not success
    assert "not the active batsman" in msg
    assert ball is None

def test_security_bat_before_bowl():
    match = GameEngine.create_match("sec_m3", 101, "bat1", 202, "bowl1")
    # Batsman tries to submit before bowler has delivered
    success, msg, ball = GameEngine.record_batsman_choice(match, batsman_id=101, number=5)
    assert not success
    assert "bowler has not bowled yet" in msg

def test_security_invalid_numbers():
    match = GameEngine.create_match("sec_m4", 101, "bat1", 202, "bowl1")
    
    # Bowler tries negative or > 6
    success, msg = GameEngine.record_bowler_choice(match, bowler_id=202, number=7)
    assert not success

    success, msg = GameEngine.record_bowler_choice(match, bowler_id=202, number=-1)
    assert not success

@pytest.mark.asyncio
async def test_admin_username_and_bot_start_stop():
    from bot.middlewares.auth_middleware import is_admin_user
    from database.json_manager import db

    # @prathamesh63 is recognized as Super Admin
    assert await is_admin_user(999999999, "prathamesh63")
    assert await is_admin_user(999999999, "@Prathamesh63")
    assert not await is_admin_user(888888888, "random_user")

    # Verify bot_enabled setting toggles cleanly
    sys_settings = await db.load("settings")
    sys_settings["bot_enabled"] = False
    await db.save("settings", sys_settings)
    assert (await db.load("settings"))["bot_enabled"] is False

    sys_settings["bot_enabled"] = True
    await db.save("settings", sys_settings)
    assert (await db.load("settings"))["bot_enabled"] is True

@pytest.mark.asyncio
async def test_rate_limit_anti_spam_and_pruning():
    from unittest.mock import AsyncMock, MagicMock
    from bot.middlewares.rate_limit_middleware import RateLimitMiddleware

    rl = RateLimitMiddleware(limit_seconds=0.0, flood_count=3, flood_window=5.0, mute_seconds=10.0)
    handler = AsyncMock(return_value="ok")

    msg = MagicMock()
    msg.reply = AsyncMock()
    user = MagicMock(id=55555)
    data = {"event_from_user": user}

    # First 2 pass, 3rd triggers flood mute
    assert await rl(handler, msg, data) == "ok"
    assert await rl(handler, msg, data) == "ok"
    res = await rl(handler, msg, data)
    assert res is None
    assert 55555 in rl.muted_until

    # Verify stale pruning keeps memory bounded
    for i in range(505):
        rl.user_last_action[100000 + i] = 0.0
    rl._prune_stale(999999999.0)
    assert len(rl.user_last_action) < 10


@pytest.mark.asyncio
async def test_administrator_and_revoke_admin():
    from unittest.mock import AsyncMock, MagicMock
    from bot.handlers.admin_handlers import cmd_administrator, cmd_revoke_admin
    from bot.middlewares.auth_middleware import is_admin_user
    from config.settings import settings

    # Grant admin by @username
    grant_msg = MagicMock()
    grant_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    grant_msg.reply_to_message = None
    grant_msg.text = "/administrator @new_mod_user"
    grant_msg.answer = AsyncMock()

    await cmd_administrator(grant_msg)
    grant_msg.answer.assert_awaited_once()
    assert "@new_mod_user is admin now" in grant_msg.answer.call_args[0][0]
    assert await is_admin_user(888002, "new_mod_user")

    # Promoted admin CANNOT stop or start the bot (only Bot Owner can)
    from bot.handlers.admin_handlers import cmd_stop_bot, cmd_start_bot
    mod_stop = MagicMock()
    mod_stop.from_user = MagicMock(id=888002, username="new_mod_user")
    mod_stop.answer = AsyncMock()
    await cmd_stop_bot(mod_stop, MagicMock())
    assert "Only the Bot Owner" in mod_stop.answer.call_args[0][0]

    mod_start = MagicMock()
    mod_start.from_user = MagicMock(id=888002, username="new_mod_user")
    mod_start.answer = AsyncMock()
    await cmd_start_bot(mod_start)
    assert "Only the Bot Owner" in mod_start.answer.call_args[0][0]

    # Revoke admin rights
    revoke_msg = MagicMock()
    revoke_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    revoke_msg.reply_to_message = None
    revoke_msg.text = "/revoke_admin @new_mod_user"
    revoke_msg.answer = AsyncMock()

    await cmd_revoke_admin(revoke_msg)
    revoke_msg.answer.assert_awaited_once()
    assert "admin rights revoked" in revoke_msg.answer.call_args[0][0]
    assert not await is_admin_user(888002, "new_mod_user")


@pytest.mark.asyncio
async def test_messege_push_broadcast():
    from unittest.mock import AsyncMock, MagicMock
    from bot.handlers.admin_handlers import cmd_messege_push
    from config.settings import settings
    from database.json_manager import db

    users = await db.load("users")
    users["70001"] = {"user_id": 70001, "username": "dm_user_1"}
    await db.save("users", users)

    mock_bot = AsyncMock()
    push_msg = MagicMock()
    push_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    push_msg.reply_to_message = None
    push_msg.text = "/messege_push Tournament tonight at 9 PM!"
    push_msg.answer = AsyncMock()

    await cmd_messege_push(push_msg, mock_bot)
    assert mock_bot.send_message.await_count >= 1
    assert "MESSAGE PUSH COMPLETE" in push_msg.answer.call_args[0][0]
