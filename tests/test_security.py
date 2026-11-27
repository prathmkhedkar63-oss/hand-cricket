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


@pytest.mark.asyncio
async def test_admin_delete_bot_message():
    from unittest.mock import AsyncMock, MagicMock
    from bot.handlers.admin_handlers import cmd_delete_bot_message
    from config.settings import settings

    mock_bot = AsyncMock()
    mock_bot.id = 8345716216

    # Non-admin blocked
    user_msg = MagicMock()
    user_msg.from_user = MagicMock(id=555111, username="regular_player")
    user_msg.answer = AsyncMock()
    await cmd_delete_bot_message(user_msg, mock_bot)
    assert "Access denied" in user_msg.answer.call_args[0][0]

    # Admin without reply receives usage prompt
    no_reply_msg = MagicMock()
    no_reply_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    no_reply_msg.reply_to_message = None
    no_reply_msg.answer = AsyncMock()
    await cmd_delete_bot_message(no_reply_msg, mock_bot)
    assert "Reply to any bot message" in no_reply_msg.answer.call_args[0][0]
    mock_bot.delete_message.assert_not_awaited()

    # Admin replying to another user's message is rejected
    other_user_msg = MagicMock()
    other_user_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    other_user_msg.reply_to_message = MagicMock(message_id=1111, from_user=MagicMock(id=555111))
    other_user_msg.answer = AsyncMock()
    await cmd_delete_bot_message(other_user_msg, mock_bot)
    assert "only delete messages sent by the bot" in other_user_msg.answer.call_args[0][0]
    mock_bot.delete_message.assert_not_awaited()

    # Admin deletes bot's replied message and trigger message
    del_msg = MagicMock()
    del_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    del_msg.chat = MagicMock(id=-100999111)
    del_msg.reply_to_message = MagicMock(message_id=4242, from_user=MagicMock(id=8345716216))
    del_msg.delete = AsyncMock()
    del_msg.answer = AsyncMock()

    await cmd_delete_bot_message(del_msg, mock_bot)
    mock_bot.delete_message.assert_awaited_once_with(chat_id=-100999111, message_id=4242)
    del_msg.delete.assert_awaited_once()

    # If deleting bot message fails, error is reported and trigger message is preserved
    failing_bot = AsyncMock()
    failing_bot.id = 8345716216
    failing_bot.delete_message = AsyncMock(side_effect=RuntimeError("message can't be deleted"))
    fail_msg = MagicMock()
    fail_msg.from_user = MagicMock(id=999001, username=settings.SUPER_ADMIN_USERNAME.lstrip("@"))
    fail_msg.chat = MagicMock(id=-100999111)
    fail_msg.reply_to_message = MagicMock(message_id=4243, from_user=MagicMock(id=8345716216))
    fail_msg.delete = AsyncMock()
    fail_msg.answer = AsyncMock()

    await cmd_delete_bot_message(fail_msg, failing_bot)
    assert "Could not delete message" in fail_msg.answer.call_args[0][0]
    fail_msg.delete.assert_not_awaited()
