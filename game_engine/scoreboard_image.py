import io
from functools import lru_cache
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from game_engine.models import InningsState, MatchState


@lru_cache(maxsize=16)
def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load a crisp TrueType font if available, falling back to Pillow default."""
    candidates = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _format_overs(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}"


def _clean_name(name: str, limit: int = 16) -> str:
    clean = (name or "Player").lstrip("@")
    return clean[:limit] + ("…" if len(clean) > limit else "")


def _to_jpeg_bytes(img: Image.Image, quality: int = 82) -> bytes:
    """Encode image to compact JPEG bytes purely in memory and close buffers immediately."""
    rgb = img.convert("RGB")
    try:
        with io.BytesIO() as buf:
            rgb.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
    finally:
        rgb.close()
        img.close()


def _draw_gradient_bg(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), (11, 16, 32))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(10 + 12 * t)
        g = int(16 + 18 * t)
        b = int(34 + 30 * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _pill_color(token: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    t = str(token).upper()
    if t == "W":
        return (200, 42, 58), (255, 255, 255)
    if t == "6":
        return (235, 168, 28), (15, 20, 35)
    if t == "4":
        return (34, 175, 96), (255, 255, 255)
    if t == "0":
        return (62, 74, 98), (220, 228, 240)
    return (44, 110, 210), (255, 255, 255)


def _over_highlight(innings: InningsState) -> Tuple[str, str]:
    last_over = innings.recent_balls[-6:]
    over_runs = 0
    over_wickets = 0
    sixes = 0
    fours = 0
    for b in last_over:
        t = str(b).upper()
        if t == "W":
            over_wickets += 1
        elif t.isdigit():
            val = int(t)
            over_runs += val
            if val == 6:
                sixes += 1
            elif val == 4:
                fours += 1

    bat = _clean_name(innings.batsman_username)
    bowl = _clean_name(innings.bowler_username)
    if over_wickets > 0 or over_runs <= 6:
        title = "🎯 TIGHT OVER" if over_wickets == 0 else "💥 WICKET OVER"
        detail = f"{bowl} conceded {over_runs} run(s)" + (f" & took {over_wickets}W!" if over_wickets else "!")
    elif over_runs >= 18:
        title = "🔥 EXPLOSIVE OVER"
        detail = f"{bat} smashed {over_runs} runs ({sixes}x6, {fours}x4)!"
    else:
        title = "⚡ OVER HIGHLIGHT"
        detail = f"{bat} scored {over_runs} runs in the over"
    return title, detail


def _compute_best_performance(match: MatchState) -> Tuple[str, str]:
    """Pick top performer across both innings using runs, boundaries, and bowling impact."""
    candidates: List[Tuple[float, str, str]] = []
    for inn in (match.first_innings, match.second_innings):
        if not inn:
            continue
        bat_name = _clean_name(inn.batsman_username, 18)
        bowl_name = _clean_name(inn.bowler_username, 18)
        sr = (inn.runs / inn.balls * 100.0) if inn.balls > 0 else 0.0
        bat_score = inn.runs * 1.5 + inn.sixes * 4 + inn.fours * 2 + (sr / 25.0 if inn.balls >= 3 else 0.0)
        if match.winner_id and inn.batsman_id == match.winner_id:
            bat_score += 8.0
        bat_line = f"{bat_name} — {inn.runs} ({inn.balls}b) • {inn.fours}x4, {inn.sixes}x6 • SR {sr:.1f}"
        candidates.append((bat_score, "🏏 BATTING MVP", bat_line))

        econ = (inn.runs / (inn.balls / 6.0)) if inn.balls > 0 else 0.0
        bowl_score = inn.wickets * 24.0 + max(0.0, 12.0 - econ) * 1.5
        if match.winner_id and inn.bowler_id == match.winner_id:
            bowl_score += 8.0
        bowl_line = f"{bowl_name} — {inn.wickets}/{inn.runs} ({_format_overs(inn.balls)} ov) • Econ {econ:.1f}"
        candidates.append((bowl_score, "🎯 BOWLING MVP", bowl_line))

    if not candidates:
        return "⭐ BEST PERFORMANCE", "Great contest!"
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, badge, line = candidates[0]
    return f"⭐ BEST PERFORMANCE ({badge.split(' ', 1)[1]})", line


class ScoreboardImageGenerator:
    """Renders lightweight in-memory JPEG scoreboards for Over End and Match End."""

    @staticmethod
    def render_over_card(match: MatchState, innings: InningsState) -> bytes:
        W, H = 800, 390
        img = _draw_gradient_bg(W, H)
        draw = ImageDraw.Draw(img)

        f_brand = _load_font(18, bold=True)
        f_title = _load_font(26, bold=True)
        f_score = _load_font(46, bold=True)
        f_sub = _load_font(20, bold=False)
        f_bold = _load_font(20, bold=True)
        f_small = _load_font(16, bold=False)

        over_num = max(1, innings.balls // 6)
        # Header bar
        draw.rectangle([0, 0, W, 56], fill=(20, 32, 62))
        draw.rectangle([0, 54, W, 57], fill=(235, 168, 28))
        draw.text((28, 17), "JPL CRICKET BOT", font=f_brand, fill=(235, 168, 28))
        header_right = f"END OF OVER {over_num} • INN {innings.innings_num}"
        draw.text((W - 28, 17), header_right, font=f_brand, fill=(220, 230, 245), anchor="ra")

        # Main score card
        draw.rounded_rectangle([24, 74, W - 24, 198], radius=14, fill=(22, 34, 64), outline=(54, 78, 128), width=2)
        bat_name = _clean_name(innings.batsman_username, 18)
        bowl_name = _clean_name(innings.bowler_username, 18)
        draw.text((44, 90), f"BAT: {bat_name}", font=f_title, fill=(255, 255, 255))
        draw.text((44, 126), f"BOWL: {bowl_name}", font=f_sub, fill=(170, 188, 218))

        score_str = f"{innings.runs}/{innings.wickets}"
        overs_str = f"({_format_overs(innings.balls)} Ov)"
        crr = (innings.runs / (innings.balls / 6.0)) if innings.balls > 0 else 0.0
        draw.text((W - 44, 86), score_str, font=f_score, fill=(255, 215, 70), anchor="ra")
        draw.text((W - 44, 142), f"{overs_str}  •  CRR {crr:.2f}", font=f_sub, fill=(195, 212, 238), anchor="ra")

        # Chase info if 2nd innings
        if innings.innings_num == 2 and innings.target:
            need = max(0, innings.target - innings.runs)
            rem = max(0, match.max_balls - innings.balls) if match.max_balls > 0 else 0
            rrr = (need / (rem / 6.0)) if rem > 0 else 0.0
            chase_txt = f"Target {innings.target} • Need {need} off {rem} balls (RRR {rrr:.2f})" if match.max_balls > 0 else f"Target {innings.target} • Need {need} more"
            draw.text((44, 166), chase_txt, font=f_small, fill=(110, 230, 165))
        else:
            draw.text((44, 166), f"Boundaries: {innings.fours}x4  •  {innings.sixes}x6", font=f_small, fill=(160, 185, 220))

        # This over balls strip
        draw.text((28, 214), "THIS OVER:", font=f_bold, fill=(200, 215, 240))
        last_balls = innings.recent_balls[-6:]
        start_x = 165
        for idx, token in enumerate(last_balls):
            cx = start_x + idx * 54
            cy = 225
            bg, fg = _pill_color(token)
            draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=bg)
            draw.text((cx, cy), str(token).upper(), font=f_bold, fill=fg, anchor="mm")

        # Best performance / Over highlight box
        hl_title, hl_detail = _over_highlight(innings)
        draw.rounded_rectangle([24, 270, W - 24, 362], radius=12, fill=(18, 46, 56), outline=(52, 168, 128), width=2)
        draw.text((44, 286), hl_title, font=f_bold, fill=(110, 240, 180))
        draw.text((44, 318), hl_detail, font=f_sub, fill=(240, 248, 255))

        return _to_jpeg_bytes(img)

    @staticmethod
    def render_match_card(match: MatchState) -> bytes:
        W, H = 800, 460
        img = _draw_gradient_bg(W, H)
        draw = ImageDraw.Draw(img)

        f_brand = _load_font(18, bold=True)
        f_title = _load_font(22, bold=True)
        f_score = _load_font(38, bold=True)
        f_sub = _load_font(18, bold=False)
        f_bold = _load_font(19, bold=True)
        f_small = _load_font(16, bold=False)

        # Header
        draw.rectangle([0, 0, W, 56], fill=(20, 32, 62))
        draw.rectangle([0, 54, W, 57], fill=(235, 168, 28))
        draw.text((28, 17), "JPL CRICKET BOT", font=f_brand, fill=(235, 168, 28))
        label = "SUPER OVER SCORECARD" if match.is_super_over else f"FINAL SCORECARD • {match.round_name.upper()}"
        draw.text((W - 28, 17), label, font=f_brand, fill=(220, 230, 245), anchor="ra")

        # Two innings side-by-side cards
        boxes = [
            (24, 76, 388, 238, "1ST INNINGS", match.first_innings),
            (412, 76, W - 24, 238, "2ND INNINGS", match.second_innings),
        ]
        for x1, y1, x2, y2, tag, inn in boxes:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=14, fill=(22, 34, 64), outline=(54, 78, 128), width=2)
            draw.text((x1 + 18, y1 + 14), tag, font=f_small, fill=(235, 168, 28))
            if inn:
                bat = _clean_name(inn.batsman_username, 17)
                sr = (inn.runs / inn.balls * 100.0) if inn.balls > 0 else 0.0
                draw.text((x1 + 18, y1 + 38), bat, font=f_title, fill=(255, 255, 255))
                draw.text((x1 + 18, y1 + 72), f"{inn.runs}/{inn.wickets}", font=f_score, fill=(255, 215, 70))
                draw.text((x1 + 148, y1 + 86), f"({_format_overs(inn.balls)} Ov)", font=f_sub, fill=(195, 212, 238))
                draw.text((x1 + 18, y1 + 126), f"4s: {inn.fours}  •  6s: {inn.sixes}  •  SR: {sr:.1f}", font=f_small, fill=(165, 185, 215))
            else:
                draw.text((x1 + 18, y1 + 65), "Did not bat", font=f_sub, fill=(150, 165, 190))

        # Result banner
        draw.rounded_rectangle([24, 256, W - 24, 326], radius=12, fill=(24, 68, 48), outline=(54, 196, 120), width=2)
        result_line = match.result_text or (f"🏆 {_clean_name(match.winner_username)} won!" if match.winner_username else "🤝 Match Tied!")
        draw.text((W // 2, 291), result_line[:56], font=f_title, fill=(255, 255, 255), anchor="mm")

        # Best Performance / MVP box
        mvp_title, mvp_line = _compute_best_performance(match)
        draw.rounded_rectangle([24, 344, W - 24, 434], radius=12, fill=(38, 30, 62), outline=(235, 168, 28), width=2)
        draw.text((44, 358), mvp_title, font=f_bold, fill=(255, 215, 70))
        draw.text((44, 392), mvp_line[:62], font=f_sub, fill=(242, 246, 255))

        return _to_jpeg_bytes(img)
