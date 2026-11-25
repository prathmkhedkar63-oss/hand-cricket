import pytest
from game_engine.engine import GameEngine
from game_engine.models import MatchStatus

def test_match_creation():
    match = GameEngine.create_match(
        match_id="test_m1",
        player1_id=101,
        player1_username="player1",
        player2_id=202,
        player2_username="player2"
    )
    assert match.status == MatchStatus.IN_PROGRESS
    assert match.current_innings == 1
    assert match.current_batsman_id == 101
    assert match.current_bowler_id == 202

def test_bowler_private_choice():
    match = GameEngine.create_match("test_m2", 101, "player1", 202, "player2")
    
    # Unauthorized bowler
    success, msg = GameEngine.record_bowler_choice(match, bowler_id=999, number=4)
    assert not success

    # Valid bowler
    success, msg = GameEngine.record_bowler_choice(match, bowler_id=202, number=4)
    assert success
    assert match.pending_bowler_number == 4

def test_wicket_and_innings_switch():
    match = GameEngine.create_match("test_m3", 101, "player1", 202, "player2", wickets_per_innings=1)
    
    # Ball 1: runs scored (bowler 4, batsman 2)
    GameEngine.record_bowler_choice(match, 202, 4)
    success, msg, ball = GameEngine.record_batsman_choice(match, 101, 2)
    assert success
    assert not ball.is_wicket
    assert ball.runs_scored == 2
    assert match.first_innings.runs == 2

    # Ball 2: Wicket! (both select 3)
    GameEngine.record_bowler_choice(match, 202, 3)
    success, msg, ball = GameEngine.record_batsman_choice(match, 101, 3)
    assert success
    assert ball.is_wicket
    assert match.first_innings.is_completed
    assert match.target == 3  # 2 + 1
    assert match.current_innings == 2
    assert match.current_batsman_id == 202
    assert match.current_bowler_id == 101

def test_chase_target_win():
    match = GameEngine.create_match("test_m4", 101, "player1", 202, "player2", wickets_per_innings=1)
    
    # 1st Innings: Out immediately on 4 (runs: 0, target: 1)
    GameEngine.record_bowler_choice(match, 202, 4)
    GameEngine.record_batsman_choice(match, 101, 4)
    assert match.target == 1

    # 2nd Innings: Player 2 bats, Player 1 bowls. Bowler chooses 2, Batsman chooses 3 -> 3 runs >= target 1 -> Win!
    GameEngine.record_bowler_choice(match, 101, 2)
    success, msg, ball = GameEngine.record_batsman_choice(match, 202, 3)
    assert success
    assert match.status == MatchStatus.COMPLETED
    assert match.winner_id == 202
    assert match.winner_username == "player2"

def test_solo_numbers_1_to_6_only():
    match = GameEngine.create_match("test_solo_16", 101, "p1", 202, "p2", mode="solo", min_number=1, max_number=6)
    ok, msg = GameEngine.record_bowler_choice(match, 202, 0)
    assert not ok
    assert "between 1 and 6" in msg

    ok, _ = GameEngine.record_bowler_choice(match, 202, 1)
    assert ok
    ok, msg, ball = GameEngine.record_batsman_choice(match, 101, 0)
    assert not ok
    assert "between 1 and 6" in msg

def test_turn_timeout_penalties_and_3_warnings():
    # 1. Bowler 3 warnings -> +6 each time -> dismissed in solo -> batsman wins
    m_solo = GameEngine.create_match("test_to_solo", 101, "bat1", 202, "bowl1", mode="solo", min_number=1, max_number=6)
    res1 = GameEngine.apply_turn_timeout_penalty(m_solo, "bowler")
    assert res1["warnings"] == 1 and m_solo.first_innings.runs == 6 and not res1["dismissed"]
    res2 = GameEngine.apply_turn_timeout_penalty(m_solo, "bowler")
    assert res2["warnings"] == 2 and m_solo.first_innings.runs == 12 and not res2["dismissed"]
    res3 = GameEngine.apply_turn_timeout_penalty(m_solo, "bowler")
    assert res3["warnings"] == 3 and m_solo.first_innings.runs == 18 and res3["dismissed"]
    assert m_solo.status == MatchStatus.COMPLETED
    assert m_solo.winner_id == 101

    # 2. Host tournament bowler 3 warnings -> paused for host/captain appointment
    m_host = GameEngine.create_match("test_to_host", 101, "bat1", 202, "bowl1", mode="host")
    GameEngine.apply_turn_timeout_penalty(m_host, "bowler")
    GameEngine.apply_turn_timeout_penalty(m_host, "bowler")
    res_h3 = GameEngine.apply_turn_timeout_penalty(m_host, "bowler")
    assert res_h3["needs_appointment"] is True
    assert m_host.status == MatchStatus.PAUSED

    # 3. Batsman 3 warnings -> -6 each time -> auto-OUT and switches to 2nd innings
    m_bat = GameEngine.create_match("test_to_bat", 101, "bat1", 202, "bowl1", mode="solo", min_number=1, max_number=6)
    m_bat.first_innings.runs = 10
    b1 = GameEngine.apply_turn_timeout_penalty(m_bat, "batsman")
    assert b1["warnings"] == 1 and m_bat.first_innings.runs == 4
    b2 = GameEngine.apply_turn_timeout_penalty(m_bat, "batsman")
    assert b2["warnings"] == 2 and m_bat.first_innings.runs == 0
    b3 = GameEngine.apply_turn_timeout_penalty(m_bat, "batsman")
    assert b3["warnings"] == 3 and b3["dismissed"] is True
    assert m_bat.current_innings == 2
    assert m_bat.target == 1

def test_commentary_engine_and_achievements():
    from game_engine.commentary import CommentaryEngine

    # Test 0 to 6 randomized commentary
    for r in range(7):
        res = CommentaryEngine.generate_ball_commentary("virat", "bumrah", r, False, 10, 10 + r, 5)
        assert res["commentary"]
        assert "virat" in res["commentary"] or "bumrah" in res["commentary"]
        assert "@" not in res["commentary"]

    # Test wicket & golden duck
    res_gd = CommentaryEngine.generate_ball_commentary("virat", "bumrah", 0, True, 0, 0, 1)
    assert res_gd["commentary"]
    assert res_gd["achievement"] is not None and "GOLDEN DUCK" in res_gd["achievement"] or "FIRST-BALL" in res_gd["achievement"]

    # Test fastest 50 (<= 15 balls)
    res_f50 = CommentaryEngine.generate_ball_commentary("virat", "bumrah", 6, False, 46, 52, 10)
    assert res_f50["achievement"] is not None and "50" in res_f50["achievement"]

    # Test 100 milestone
    res_100 = CommentaryEngine.generate_ball_commentary("virat", "bumrah", 4, False, 96, 100, 30)
    assert res_100["achievement"] is not None and any(
        k in res_100["achievement"] for k in ["100", "CENTURY", "TON UP", "triple figures"]
    )

    # Test hat-trick of sixes
    res_ht = CommentaryEngine.generate_ball_commentary("virat", "bumrah", 6, False, 12, 18, 3, recent_runs=[6, 6, 6])
    assert res_ht["achievement"] is not None and any(
        k in res_ht["achievement"] for k in ["SIXES", "6, 6, 6", "THREE IN A ROW", "maximums"]
    )

def test_scoreboard_crr_rrr_chase_meter_and_summary():
    from game_engine.scoreboard import ScoreboardFormatter

    match = GameEngine.create_match("test_sb_1", 101, "p1", 202, "p2", max_balls=12)
    # Ball 1: 4 runs, Ball 2: 6 runs, Ball 3: Wicket
    GameEngine.record_bowler_choice(match, 202, 2)
    GameEngine.record_batsman_choice(match, 101, 4)
    GameEngine.record_bowler_choice(match, 202, 3)
    GameEngine.record_batsman_choice(match, 101, 6)
    GameEngine.record_bowler_choice(match, 202, 5)
    GameEngine.record_batsman_choice(match, 101, 5)

    assert match.first_innings.fours == 1
    assert match.first_innings.sixes == 1
    assert match.first_innings.recent_balls == ["4", "6", "W"]
    assert match.current_innings == 2
    assert match.target == 11

    # 2nd innings ball 1: 2 runs
    GameEngine.record_bowler_choice(match, 101, 4)
    GameEngine.record_batsman_choice(match, 202, 2)

    sb = ScoreboardFormatter.format_live_scoreboard(match)
    assert "CRR:" in sb
    assert "Chase Meter:" in sb
    assert "RRR:" in sb
    assert "This Over: 2 (2 runs)" in sb

    summary = ScoreboardFormatter.format_match_summary(match)
    assert "MATCH SUMMARY" in summary
    assert "Man of the Match:" in summary
    assert "4s:" in summary and "6s:" in summary
    assert "@" not in summary

def test_2line_commentary_and_lightweight_assets():
    from game_engine.commentary import CommentaryEngine
    from bot.services.media_service import MediaService

    res = CommentaryEngine.generate_ball_commentary("virat", "bumrah", 6, False, 10, 16, 4)
    assert "\n" in res["commentary"]
    assert len(res["commentary"].splitlines()) == 2
    assert "@" not in res["commentary"]

    for key, path in MediaService.IMAGES.items():
        assert path.exists(), f"Missing image asset: {key}"
        assert path.stat().st_size < 50 * 1024, f"Asset {key} too large"

def test_super_over_on_tie():
    match = GameEngine.create_match("test_so_1", 101, "p1", 202, "p2", max_balls=1, wickets_per_innings=1)
    # 1st innings: 1 ball -> 4 runs (target 5)
    GameEngine.record_bowler_choice(match, 202, 2)
    GameEngine.record_batsman_choice(match, 101, 4)
    assert match.current_innings == 2
    assert match.target == 5

    # 2nd innings: 1 ball -> 4 runs -> TIED!
    GameEngine.record_bowler_choice(match, 101, 2)
    GameEngine.record_batsman_choice(match, 202, 4)
    assert match.status == MatchStatus.TIED

    # Trigger Super Over
    started = GameEngine.start_super_over(match)
    assert started is True
    assert match.is_super_over is True
    assert match.status == MatchStatus.IN_PROGRESS
    assert match.max_balls == 6
    assert match.current_batsman_id == 202  # 2nd innings chaser bats first in Super Over
    assert match.current_bowler_id == 101

def test_bot_psychology_engine_and_randomizer():
    from game_engine.bot_ai import BotPsychologyEngine

    # 1. Persona profiling: Double-Tapper vs Switcher
    dt_profile = BotPsychologyEngine.profile_player([6, 6, 6, 4, 4, 4])
    assert dt_profile["repeat_rate"] > 0.25
    assert dt_profile["greed_index"] == 1.0

    sw_profile = BotPsychologyEngine.profile_player([1, 4, 2, 5, 3, 6])
    assert sw_profile["repeat_rate"] < 0.15

    # 2. Non-deterministic randomized action sampling across repeated trials
    bowl_samples = [
        BotPsychologyEngine.choose_bowling_number(
            human_bat_history=[1, 1, 2, 1],
            human_runs=47,  # Nervous 40s trigger
            balls_played=10,
            innings_num=2,
            target=60,
            max_balls=12
        )
        for _ in range(30)
    ]
    assert all(0 <= x <= 6 for x in bowl_samples)
    assert len(set(bowl_samples)) > 1  # Randomized, never a fixed single step

    bat_samples = [
        BotPsychologyEngine.choose_batting_number(
            human_bowl_history=[6, 4, 6, 6],
            bot_runs=10,
            balls_played=4,
            innings_num=2,
            target=15,
            max_balls=12,
            last_bot_shot=6  # Tilt avoidance
        )
        for _ in range(30)
    ]
    assert all(0 <= x <= 6 for x in bat_samples)
    assert len(set(bat_samples)) > 1

@pytest.mark.asyncio
async def test_typed_inputs_dm_button_reactions_and_challenge_bot():
    import uuid
    from unittest.mock import AsyncMock, MagicMock
    from bot.keyboards.game_keyboards import get_go_to_dm_keyboard
    from bot.handlers.game_handlers import on_private_typed_input, on_group_typed_input
    from bot.services.game_service import GameService
    from game_engine.bot_ai import BotPsychologyEngine

    # 1. Go to Bot DM URL button
    kb = get_go_to_dm_keyboard("@TestCricketBot")
    btn = kb.inline_keyboard[0][0]
    assert "Go to Bot DM" in btn.text
    assert btn.url == "https://t.me/TestCricketBot"

    # 2. Setup a 1v1 match where human bats first vs BotPsychologyEngine
    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=999)
    mock_bot._me = MagicMock(username="TestCricketBot")

    m_id = f"test_cb_{uuid.uuid4().hex[:6]}"
    match = await GameService.start_new_match(
        match_id=m_id,
        player1_id=3001,
        player1_username="human3001",
        player2_id=BotPsychologyEngine.BOT_USER_ID,
        player2_username=BotPsychologyEngine.BOT_USERNAME,
        group_chat_id=-100888999,
        bot=mock_bot,
        max_balls=12,
        mode="host",
        min_number=0,
        max_number=6
    )
    # Bot was bowler, so it already bowled its secret choice immediately!
    assert match.pending_bowler_number is not None

    # 3. Non-numeric input in group by active batsman -> validation error reply
    bad_msg = MagicMock()
    bad_msg.from_user = MagicMock(id=3001)
    bad_msg.chat = MagicMock(id=-100888999)
    bad_msg.text = "hello"
    bad_msg.reply = AsyncMock()
    bad_msg.react = AsyncMock()
    await on_group_typed_input(bad_msg, mock_bot)
    bad_msg.reply.assert_awaited_once()
    assert "Invalid input" in bad_msg.reply.call_args[0][0]

    # 4. Valid typed number in group -> resolves ball & triggers positive reaction
    good_msg = MagicMock()
    good_msg.from_user = MagicMock(id=3001)
    good_msg.chat = MagicMock(id=-100888999)
    good_msg.text = "4"
    good_msg.reply = AsyncMock()
    good_msg.react = AsyncMock()
    await on_group_typed_input(good_msg, mock_bot)
    good_msg.react.assert_awaited_once()

    GameService.cleanup_match_cache(m_id)


@pytest.mark.asyncio
async def test_dynamic_scoreboard_images_and_db_auto_cleanup():
    import uuid
    from game_engine.scoreboard_image import ScoreboardImageGenerator
    from bot.services.game_service import GameService
    from database.json_manager import db

    m_id = f"m_img_{uuid.uuid4().hex[:6]}"
    match = GameEngine.create_match(m_id, 1, "virat", 2, "bumrah", max_balls=12)
    for b in [6, 4, 1, 6, 0, 4]:
        GameEngine.record_bowler_choice(match, 2, 5)
        GameEngine.record_batsman_choice(match, 1, b)

    over_bytes = ScoreboardImageGenerator.render_over_card(match, match.first_innings)
    assert over_bytes.startswith(b"\xff\xd8\xff")
    assert len(over_bytes) < 65 * 1024

    live_bytes = ScoreboardImageGenerator.render_over_card(
        match, match.first_innings, title_override="LIVE SCORECARD • INN 1"
    )
    assert live_bytes.startswith(b"\xff\xd8\xff")

    # Finish 1st & 2nd innings
    GameEngine.record_bowler_choice(match, 2, 3)
    GameEngine.record_batsman_choice(match, 1, 3)
    GameEngine.record_bowler_choice(match, 1, 6)
    GameEngine.record_batsman_choice(match, 2, 6)

    match_bytes = ScoreboardImageGenerator.render_match_card(match)
    assert match_bytes.startswith(b"\xff\xd8\xff")
    assert len(match_bytes) < 65 * 1024

    # Verify DB auto-cleanup removes ball_history for completed match
    history = await db.load("ball_history")
    history.append({"match_id": m_id, "runs_scored": 6})
    await db.save("ball_history", history)
    await GameService.cleanup_match_db(m_id)
    after = await db.load("ball_history")
    assert not any(isinstance(v, dict) and v.get("match_id") == m_id for v in after)

    # Verify all mapped MP4 clips exist in assets/videos/
    from bot.services.media_service import MediaService
    for key, filenames in MediaService.VIDEOS.items():
        assert filenames
        for fname in filenames:
            assert MediaService._resolve_video_path(fname) is not None, f"Missing video {fname} for {key}"
