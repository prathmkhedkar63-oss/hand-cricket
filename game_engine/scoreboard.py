from typing import Optional, List
from game_engine.models import MatchState, InningsState, BallEvent, MatchStatus
from game_engine.commentary import CommentaryEngine

class ScoreboardFormatter:
    """
    Generates beautiful, compliant Telegram live scoreboards, over summaries,
    chase meters, match summary cards, and ball outcome messages.
    """

    @staticmethod
    def _format_overs(balls: int) -> str:
        return f"{balls // 6}.{balls % 6}"

    @staticmethod
    def _format_crr(runs: int, balls: int) -> str:
        if balls <= 0:
            return "0.00"
        return f"{(runs / balls) * 6:.2f}"

    @staticmethod
    def _format_over_summary(inn: InningsState) -> str:
        if not inn or not inn.recent_balls:
            return ""
        # Show the current/just-completed over (up to 6 balls)
        rem = len(inn.recent_balls) % 6
        slice_len = 6 if rem == 0 else rem
        over_balls = inn.recent_balls[-slice_len:]
        over_runs = sum(int(b) for b in over_balls if b.isdigit())
        label = "Last Over" if rem == 0 else "This Over"
        return f"{label}: {' • '.join(over_balls)} ({over_runs} runs)"

    @staticmethod
    def _format_chase_meter(match: MatchState, second_inn: InningsState) -> str:
        if match.target is None or match.status in [MatchStatus.COMPLETED, MatchStatus.TIED]:
            return ""
        needed = max(0, match.target - second_inn.runs)
        pct = min(1.0, second_inn.runs / max(1, match.target))
        filled = int(round(pct * 10))
        bar = "█" * filled + "░" * (10 - filled)

        if match.max_balls > 0:
            balls_left = max(0, match.max_balls - second_inn.balls)
            rrr = f"{(needed / balls_left) * 6:.2f}" if balls_left > 0 else "∞"
            return (
                f"📊 <b>Chase Meter:</b> [{bar}] {int(pct * 100)}%\n"
                f"🎯 Need <b>{needed}</b> run(s) from <b>{balls_left}</b> ball(s) | RRR: <b>{rrr}</b>\n"
            )
        return (
            f"📊 <b>Chase Meter:</b> [{bar}] {int(pct * 100)}%\n"
            f"🎯 Need <b>{needed}</b> run(s) to win\n"
        )

    @staticmethod
    def format_live_scoreboard(match: MatchState) -> str:
        p1 = (match.player1_username or f"Player {match.player1_id}").lstrip("@")
        p2 = (match.player2_username or f"Player {match.player2_id}").lstrip("@")

        first_inn = match.first_innings
        second_inn = match.second_innings

        # 1st Innings string
        if first_inn:
            f_batsman = first_inn.batsman_username.lstrip("@")
            f_bowler = first_inn.bowler_username.lstrip("@")
            f_overs = ScoreboardFormatter._format_overs(first_inn.balls)
            f_crr = ScoreboardFormatter._format_crr(first_inn.runs, first_inn.balls)
            f_text = (
                f"Batsman: <b>{f_batsman}</b> | Bowler: <b>{f_bowler}</b>\n"
                f"Score: <b>{first_inn.runs}/{first_inn.wickets}</b> "
                f"({f_overs} Ov | CRR: {f_crr})"
            )
            f_over_line = ScoreboardFormatter._format_over_summary(first_inn)
            if f_over_line and match.current_innings == 1:
                f_text += f"\n{f_over_line}"
            if first_inn.is_completed:
                f_text += f"\nStatus: Completed ({first_inn.dismissal_reason or 'End'})"
        else:
            f_text = "Pending"

        # 2nd Innings string
        if second_inn:
            s_batsman = second_inn.batsman_username.lstrip("@")
            s_bowler = second_inn.bowler_username.lstrip("@")
            s_overs = ScoreboardFormatter._format_overs(second_inn.balls)
            s_crr = ScoreboardFormatter._format_crr(second_inn.runs, second_inn.balls)
            s_text = (
                f"Batsman: <b>{s_batsman}</b> | Bowler: <b>{s_bowler}</b>\n"
                f"Score: <b>{second_inn.runs}/{second_inn.wickets}</b> "
                f"({s_overs} Ov | CRR: {s_crr})"
            )
            s_over_line = ScoreboardFormatter._format_over_summary(second_inn)
            if s_over_line and match.current_innings == 2:
                s_text += f"\n{s_over_line}"
            if second_inn.is_completed:
                s_text += f"\nStatus: Completed ({second_inn.dismissal_reason or 'End'})"
        else:
            s_text = "Pending"

        target_str = str(match.target) if match.target is not None else "Pending"
        status_display = match.status.value.replace("_", " ").upper()
        title = "🔥 <b>JPL CRICKET BOT • SUPER OVER</b>" if match.is_super_over else "🏏 <b>JPL CRICKET BOT • SCORECARD</b>"

        text = (
            f"{title}\n\n"
            f"⚔️ <b>{p1} VS {p2}</b> ({match.round_name})\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"🥇 <b>FIRST INNINGS</b>\n"
            f"{f_text}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"🥈 <b>SECOND INNINGS</b>\n"
            f"{s_text}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"🎯 <b>TARGET:</b> {target_str}\n"
        )

        if second_inn and match.current_innings == 2:
            text += ScoreboardFormatter._format_chase_meter(match, second_inn)

        text += f"⚡ <b>STATUS:</b> {status_display}\n"

        if match.status == MatchStatus.COMPLETED and match.result_text:
            clean_res = match.result_text.replace("@", "")
            text += f"\n🏆 <b>RESULT:</b> {clean_res}"

        return text

    @staticmethod
    def format_match_summary(match: MatchState) -> str:
        """
        Generates a clean post-match summary card with 4s, 6s, Strike Rate, and Man of the Match (no @ tags).
        """
        def _inn_line(inn: Optional[InningsState], label: str) -> str:
            if not inn:
                return f"{label}: Did not bat"
            sr = f"{(inn.runs / inn.balls) * 100:.1f}" if inn.balls > 0 else "0.0"
            b_name = inn.batsman_username.lstrip("@")
            return (
                f"👤 <b>{b_name}</b>: <b>{inn.runs}/{inn.wickets}</b> ({inn.balls}b)\n"
                f"   ⚡ SR: <b>{sr}</b> | 4s: <b>{inn.fours}</b> | 6s: <b>{inn.sixes}</b>"
            )

        p1_score = 0.0
        p2_score = 0.0
        if match.first_innings:
            f = match.first_innings
            p1_score += f.runs + (f.fours * 1.5) + (f.sixes * 2.5)
            p2_score += f.wickets * 15
        if match.second_innings:
            s = match.second_innings
            p2_score += s.runs + (s.fours * 1.5) + (s.sixes * 2.5)
            p1_score += s.wickets * 15

        if match.winner_id == match.player1_id:
            p1_score += 20
        elif match.winner_id == match.player2_id:
            p2_score += 20

        motm = (match.player1_username if p1_score >= p2_score else match.player2_username).lstrip("@")
        p1_clean = match.player1_username.lstrip("@")
        p2_clean = match.player2_username.lstrip("@")
        winner_clean = (match.winner_username or "Tie").lstrip("@")
        res_clean = (match.result_text or "").replace("@", "")

        return (
            f"📋 <b>JPL CRICKET BOT • MATCH SUMMARY</b>\n\n"
            f"⚔️ <b>{p1_clean}</b> VS <b>{p2_clean}</b>\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"{_inn_line(match.first_innings, '1st Innings')}\n\n"
            f"{_inn_line(match.second_innings, '2nd Innings')}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"🏆 <b>Winner:</b> <b>{winner_clean}</b>\n"
            f"📝 {res_clean}\n"
            f"🏅 <b>Man of the Match:</b> <b>{motm}</b>"
        )

    @staticmethod
    def format_ball_result(
        ball: BallEvent,
        match: MatchState,
        recent_runs: Optional[List[int]] = None
    ) -> str:
        batsman = ball.batsman_username.lstrip("@")
        bowler = ball.bowler_username.lstrip("@")
        current_inn = match.second_innings if ball.innings_num == 2 else match.first_innings
        score_str = f"{current_inn.runs}/{current_inn.wickets}" if current_inn else "0/0"
        overs_str = ScoreboardFormatter._format_overs(ball.ball_number)
        new_runs = current_inn.runs if current_inn else ball.current_score
        prev_runs = max(0, new_runs - ball.runs_scored)

        comm = CommentaryEngine.generate_ball_commentary(
            batsman_username=batsman,
            bowler_username=bowler,
            runs_scored=ball.runs_scored,
            is_wicket=ball.is_wicket,
            prev_runs=prev_runs,
            new_runs=new_runs,
            ball_number=ball.ball_number,
            recent_runs=recent_runs
        )

        if ball.is_wicket:
            header = f"💥 <b>OUT!</b> <b>{batsman}</b> ({ball.batsman_number}) = <b>{bowler}</b> ({ball.bowler_number}) | <b>{score_str}</b> ({overs_str} Ov)"
        else:
            header = f"🏏 <b>{batsman}</b>: <b>{ball.batsman_number}</b> | <b>{bowler}</b>: <b>{ball.bowler_number}</b> ➡️ <b>+{ball.runs_scored}</b> (<b>{score_str}</b> • {overs_str} Ov)"

        text = f"{header}\n🎙️ <i>{comm['commentary']}</i>"
        if comm.get("achievement"):
            text += f"\n🏅 <b>{comm['achievement']}</b>"

        if match.target and ball.innings_num == 2 and not match.status in [MatchStatus.COMPLETED, MatchStatus.TIED]:
            needed = max(0, match.target - current_inn.runs)
            text += f"\n🎯 Need <b>{needed}</b> to win"

        return text
