import pytest
from bot.services.tournament_service import TournamentService
from database.json_manager import db

def test_bracket_generation_even():
    players = [
        {"user_id": 1, "username": "p1"},
        {"user_id": 2, "username": "p2"},
        {"user_id": 3, "username": "p3"},
        {"user_id": 4, "username": "p4"}
    ]
    fixtures, byes = TournamentService.generate_single_elimination_bracket(players, shuffle=False)
    assert len(fixtures) == 2
    assert len(byes) == 0
    assert fixtures[0]["player1"]["username"] == "p1"
    assert fixtures[0]["player2"]["username"] == "p2"

def test_bracket_generation_odd_with_byes():
    players = [
        {"user_id": 1, "username": "p1"},
        {"user_id": 2, "username": "p2"},
        {"user_id": 3, "username": "p3"}
    ]
    # For 3 players, next power of 2 is 4, so 1 bye awarded, 1 match played
    fixtures, byes = TournamentService.generate_single_elimination_bracket(players, shuffle=False)
    assert len(byes) == 1
    assert len(fixtures) == 1
    assert byes[0]["username"] == "p1"
    assert fixtures[0]["player1"]["username"] == "p2"
    assert fixtures[0]["player2"]["username"] == "p3"

@pytest.mark.asyncio
async def test_dynamic_group_binding():
    t = await TournamentService.create_tournament(
        tournament_id="t_dyn_1",
        name="Dynamic Arena Cup",
        description="Test",
        mode="solo",
        group_chat_id=None,
        creator_id=123
    )
    assert t["group_chat_id"] is None

    # Host or Admin binds to group -100999888
    tournaments = await db.load("tournaments")
    tournaments["t_dyn_1"]["group_chat_id"] = -100999888
    await db.save("tournaments", tournaments)

    reloaded = await db.get("tournaments", "t_dyn_1")
    assert reloaded["group_chat_id"] == -100999888

@pytest.mark.asyncio
async def test_host_claim_and_team_commands():
    import uuid
    from bot.services.host_tournament_service import HostTournamentService

    t_id = f"t_host_test_{uuid.uuid4().hex[:6]}"
    await TournamentService.create_tournament(
        tournament_id=t_id,
        name="Host Championship Test",
        description="Testing host flow",
        mode="host",
        group_chat_id=-10012345,
        creator_id=999
    )

    # 1. Add players to Team A and Team B
    success, msg = await HostTournamentService.manage_teams(t_id, "Team A", "add", 101, "virat")
    assert success
    success, msg = await HostTournamentService.manage_teams(t_id, "Team A", "add", 102, "rohit")
    assert success
    success, msg = await HostTournamentService.manage_teams(t_id, "Team B", "add", 201, "bumrah")
    assert success
    success, msg = await HostTournamentService.manage_teams(t_id, "Team B", "add", 202, "shami")
    assert success

    # 2. Set Captains
    success, msg = await HostTournamentService.set_captain(t_id, "Team A", 101, "virat")
    assert success
    success, msg = await HostTournamentService.set_captain(t_id, "Team B", 201, "bumrah")
    assert success

    # 3. Verify teams and captains
    teams = await HostTournamentService.get_teams(t_id)
    assert len(teams["Team A"]) == 2
    assert len(teams["Team B"]) == 2
    assert teams["captains"]["Team A"]["username"] == "virat"
    assert teams["captains"]["Team B"]["username"] == "bumrah"

@pytest.mark.asyncio
async def test_solo_force_start_and_countdown_registration():
    import uuid
    from unittest.mock import AsyncMock, MagicMock
    from bot.services.solo_tournament_service import SoloTournamentService

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=12345)
    mock_bot.send_photo.return_value = MagicMock(message_id=12345, photo=None)
    t_id = f"t_solo_force_{uuid.uuid4().hex[:6]}"
    await TournamentService.create_tournament(
        tournament_id=t_id,
        name="Force Start Cup",
        description="Test solo force start",
        mode="solo",
        group_chat_id=-100555666,
        creator_id=777
    )

    # Creator joins and starts countdown with 1 player
    ok, _ = await TournamentService.register_player(t_id, 777, "creator777")
    assert ok
    ok, msg = await SoloTournamentService.start_countdown(t_id, mock_bot, -100555666)
    assert ok

    # Force start with < 2 players should fail even for an admin
    ok, msg = await SoloTournamentService.force_start(t_id, mock_bot, actor_id=777, actor_username="creator777", is_group_admin=True)
    assert not ok
    assert "at least 2" in msg

    # Second player registers during 'countdown' status
    ok, _ = await TournamentService.register_player(t_id, 888, "challenger888")
    assert ok

    # Non-admin creator cannot force start
    ok, msg = await SoloTournamentService.force_start(t_id, mock_bot, actor_id=777, actor_username="creator777", is_group_admin=False)
    assert not ok
    assert "group admins" in msg.lower()

    # @prathamesh63 (or group admin) force starts with 2 players
    ok, msg = await SoloTournamentService.force_start(t_id, mock_bot, actor_id=99999, actor_username="prathamesh63", is_group_admin=False)
    assert ok
    t = await db.get("tournaments", t_id)
    assert t["status"] == "active"

    # Cancel any leftover countdown task just in case
    task = SoloTournamentService._running_countdowns.pop(t_id, None)
    if task and not task.done():
        task.cancel()

@pytest.mark.asyncio
async def test_team_max_11_remove_swap_and_ball_batching():
    import uuid
    from bot.services.host_tournament_service import HostTournamentService
    from bot.services.game_service import GameService

    t_id = f"t_cap11_{uuid.uuid4().hex[:6]}"
    await TournamentService.create_tournament(
        tournament_id=t_id,
        name="11 Squad Cup",
        description="Test 11 cap and swap",
        mode="host",
        group_chat_id=-100777888,
        creator_id=500
    )

    # Add 11 players to Team A
    for i in range(1, 12):
        ok, _ = await HostTournamentService.manage_teams(t_id, "Team A", "add", 1000 + i, f"a_player_{i}")
        assert ok

    # 12th player must be rejected
    ok, msg = await HostTournamentService.manage_teams(t_id, "Team A", "add", 1012, "a_player_12")
    assert not ok
    assert "11" in msg

    # Set player 1 as Captain, then swap slot #1 with a substitute
    await HostTournamentService.set_captain(t_id, "Team A", 1001, "a_player_1")
    ok, swap_msg = await HostTournamentService.swap_player(t_id, 1, 2001, "sub_impact")
    assert ok
    teams = await HostTournamentService.get_teams(t_id)
    assert teams["Team A"][0]["username"] == "sub_impact"
    assert teams["captains"]["Team A"]["username"] == "sub_impact"

    # Remove player from Team A
    ok, _ = await HostTournamentService.manage_teams(t_id, "Team A", "remove", 1002, "a_player_2")
    assert ok
    teams = await HostTournamentService.get_teams(t_id)
    assert len(teams["Team A"]) == 10

    # Verify zero-lag ball batching flush
    GameService._pending_balls.append({"ball_id": "batch_b1", "runs": 6})
    await GameService.flush_pending_balls()
    assert len(GameService._pending_balls) == 0
    history = await db.load("ball_history")
    assert any(b.get("ball_id") == "batch_b1" for b in history)
