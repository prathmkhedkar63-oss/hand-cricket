"""
Generates lightweight (~15-25 KB) esports-themed JPEG banners for JPL CRICKET BOT.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

BANNERS = [
    {
        "filename": "welcome.jpg",
        "bg_top": (10, 22, 34),
        "bg_bot": (16, 65, 52),
        "accent": (16, 185, 129),
        "gold": (245, 158, 11),
        "tag": "OFFICIAL ARENA",
        "title": "JPL CRICKET BOT",
        "subtitle": "SOLO KNOCKOUTS  •  TEAM LEAGUES  •  1v1 BOT",
    },
    {
        "filename": "match_start.jpg",
        "bg_top": (12, 18, 38),
        "bg_bot": (14, 74, 110),
        "accent": (56, 189, 248),
        "gold": (16, 185, 129),
        "tag": "LIVE ACTION",
        "title": "MATCH STARTED",
        "subtitle": "JPL CRICKET BOT  •  STEP UP TO THE CREASE",
    },
    {
        "filename": "six.jpg",
        "bg_top": (34, 14, 14),
        "bg_bot": (124, 45, 18),
        "accent": (249, 115, 22),
        "gold": (250, 204, 21),
        "tag": "MAXIMUM HIT",
        "title": "SMASHED FOR SIX!",
        "subtitle": "JPL CRICKET BOT  •  OUT OF THE PARK",
    },
    {
        "filename": "wicket.jpg",
        "bg_top": (28, 10, 18),
        "bg_bot": (127, 29, 29),
        "accent": (239, 68, 68),
        "gold": (248, 113, 113),
        "tag": "BREAKTHROUGH",
        "title": "WICKET! OUT!",
        "subtitle": "JPL CRICKET BOT  •  STUMPS SHATTERED",
    },
    {
        "filename": "champion.jpg",
        "bg_top": (18, 16, 36),
        "bg_bot": (92, 65, 14),
        "accent": (245, 158, 11),
        "gold": (253, 224, 71),
        "tag": "VICTORY",
        "title": "MATCH & CHAMPIONS",
        "subtitle": "JPL CRICKET BOT  •  GLORY IN THE ARENA",
    },
]

def _load_font(size: int, bold: bool = True):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def generate_all():
    W, H = 800, 360
    font_tag = _load_font(20, bold=True)
    font_title = _load_font(56, bold=True)
    font_sub = _load_font(20, bold=False)

    for b in BANNERS:
        img = Image.new("RGB", (W, H), b["bg_top"])
        draw = ImageDraw.Draw(img)

        # Smooth vertical gradient
        for y in range(H):
            t = y / H
            r = int(b["bg_top"][0] * (1 - t) + b["bg_bot"][0] * t)
            g = int(b["bg_top"][1] * (1 - t) + b["bg_bot"][1] * t)
            bl = int(b["bg_top"][2] * (1 - t) + b["bg_bot"][2] * t)
            draw.line([(0, y), (W, y)], fill=(r, g, bl))

        # Subtle geometric stadium accent lines
        draw.rectangle([(0, 0), (W, 8)], fill=b["accent"])
        draw.rectangle([(0, H - 8), (W, H)], fill=b["gold"])
        draw.ellipse([(-80, -80), (220, 220)], outline=b["accent"], width=3)
        draw.ellipse([(W - 220, H - 220), (W + 80, H + 80)], outline=b["gold"], width=3)

        # Tag pill
        tag_bbox = draw.textbbox((0, 0), b["tag"], font=font_tag)
        tw = tag_bbox[2] - tag_bbox[0]
        pill_x1 = (W - tw) // 2 - 22
        pill_x2 = (W + tw) // 2 + 22
        draw.rounded_rectangle([(pill_x1, 78), (pill_x2, 114)], radius=18, fill=b["accent"])
        draw.text((W // 2, 96), b["tag"], fill=(10, 15, 25), font=font_tag, anchor="mm")

        # Main title
        draw.text((W // 2 + 2, 178), b["title"], fill=(0, 0, 0), font=font_title, anchor="mm")
        draw.text((W // 2, 175), b["title"], fill=(255, 255, 255), font=font_title, anchor="mm")

        # Divider bar
        draw.rounded_rectangle([(W // 2 - 90, 222), (W // 2 + 90, 227)], radius=3, fill=b["gold"])

        # Subtitle
        draw.text((W // 2, 265), b["subtitle"], fill=(226, 232, 240), font=font_sub, anchor="mm")

        out_path = ASSETS_DIR / b["filename"]
        img.save(out_path, "JPEG", quality=72, optimize=True)
        size_kb = out_path.stat().st_size / 1024
        print(f"Generated {out_path.name}: {size_kb:.1f} KB")

if __name__ == "__main__":
    generate_all()
