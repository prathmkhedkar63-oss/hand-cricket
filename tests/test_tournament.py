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


def test_solo_rotation_out_over_and_midover_bowler_takeover():
    from game_engine.engine import GameEngine
    from game_engine.models import MatchStatus
    from game_engine.scoreboard import ScoreboardFormatter
    from game_engine.scoreboard_image import ScoreboardImageGenerator

    roster = [
        {"user_id": 1, "username": "p1"},
        {"user_id": 2, "username": "p2"},
        {"user_id": 3, "username": "p3"},
        {"user_id": 4, "username": "p4"},
    ]

    # Scenario A: 6-ball over completes -> batsman stays, bowler rotates 2 -> 3
    m1 = GameEngine.create_solo_rotation_match("sr_test_1", roster, tournament_id="t1")
    assert m1.current_batsman_username == "p1"
    assert m1.current_bowler_username == "p2"

    for _ in range(6):
        GameEngine.record_bowler_choice(m1, 2, 1)
        ok, _, _ = GameEngine.record_batsman_choice(m1, 1, 4)
        assert ok

    assert m1.solo_completed_overs == 1
    assert m1.solo_over_balls == 0
    assert m1.current_batsman_username == "p1"  # Batsman only changes on OUT!
    assert m1.current_bowler_username == "p3"   # Bowler rotated 2 -> 3 after 6 balls
    assert m1.solo_player_stats["1"]["runs"] == 24

    # Ball 1 & 2 of Over 2: P3 bowls ball 1 (2 runs), ball 2 (P1 OUT!)
    GameEngine.record_bowler_choice(m1, 3, 2)
    GameEngine.record_batsman_choice(m1, 1, 5)
    GameEngine.record_bowler_choice(m1, 3, 4)
    GameEngine.record_batsman_choice(m1, 1, 4)  # Wicket!
    assert m1.current_batsman_username == "p2"  # 1 out -> 2 bats
    assert m1.current_bowler_username == "p3"   # P3 != P2, so P3 continues Over 2!
    assert m1.solo_over_balls == 2              # Over still continues (4 balls left)
    assert m1.first_innings.runs == 0           # Fresh batting score for P2

    # P3 finishes remaining 4 balls of Over 2 -> Over 2 completes -> rotates to P4
    for _ in range(4):
        GameEngine.record_bowler_choice(m1, 3, 1)
        GameEngine.record_batsman_choice(m1, 2, 2)
    assert m1.solo_completed_overs == 2
    assert m1.solo_over_balls == 0
    assert m1.current_batsman_username == "p2"
    assert m1.current_bowler_username == "p4"

    # Scenario B: Mid-over wicket where new batsman WAS bowling -> next bowler takes over remaining over
    m2 = GameEngine.create_solo_rotation_match("sr_test_2", roster, tournament_id="t2")
    # Ball 1 of Over 1: P2 bowls to P1 -> 6 runs
    GameEngine.record_bowler_choice(m2, 2, 1)
    GameEngine.record_batsman_choice(m2, 1, 6)
    # Ball 2 of Over 1: P2 bowls 3, P1 bats 3 -> OUT!
    GameEngine.record_bowler_choice(m2, 2, 3)
    GameEngine.record_batsman_choice(m2, 1, 3)

    assert m2.current_batsman_username == "p2"  # P2 becomes batsman
    assert m2.solo_over_balls == 2              # Over 1 still at 2/6 balls
    assert m2.current_bowler_username == "p3"   # P3 took over remaining 4 balls of Over 1!

    # P3 finishes remaining 4 balls of Over 1 (balls 3..6)
    for _ in range(4):
        GameEngine.record_bowler_choice(m2, 3, 2)
        GameEngine.record_batsman_choice(m2, 2, 6)
    assert m2.solo_completed_overs == 1
    assert m2.solo_over_balls == 0
    assert m2.current_batsman_username == "p2"
    assert m2.current_bowler_username == "p4"   # Cycle: P3 -> P4

    # Get P2 out to P4 -> P3 bats -> P4 finishes 5 balls -> over completes -> bowler cycles to P1!
    GameEngine.record_bowler_choice(m2, 4, 5)
    GameEngine.record_batsman_choice(m2, 2, 5)  # P2 out on 24 runs!
    assert m2.current_batsman_username == "p3"
    assert m2.current_bowler_username == "p4"
    assert m2.solo_over_balls == 1

    for _ in range(5):
        GameEngine.record_bowler_choice(m2, 4, 1)
        GameEngine.record_batsman_choice(m2, 3, 2)
    assert m2.solo_completed_overs == 2
    assert m2.current_bowler_username == "p1"   # Cycle wrapped around to P1!

    # Get P3 out -> P4 bats -> get P4 out -> match completes, P2 (24 runs) wins!
    GameEngine.record_bowler_choice(m2, 1, 3)
    GameEngine.record_batsman_choice(m2, 3, 3)  # P3 out (10 runs)
    assert m2.current_batsman_username == "p4"
    assert m2.current_bowler_username == "p1"

    GameEngine.record_bowler_choice(m2, 1, 4)
    GameEngine.record_batsman_choice(m2, 4, 4)  # P4 out (0 runs)
    assert m2.status == MatchStatus.COMPLETED
    assert m2.winner_username == "p2"

    # Verify text & image scoreboards render cleanly for solo rotation
    sb = ScoreboardFormatter.format_match_summary(m2)
    assert "p2" in sb
    img_over = ScoreboardImageGenerator.render_over_card(m2, m2.first_innings)
    img_match = ScoreboardImageGenerator.render_match_card(m2)
    assert img_over.startswith(b"\xff\xd8\xff")
    assert img_match.startswith(b"\xff\xd8\xff")
