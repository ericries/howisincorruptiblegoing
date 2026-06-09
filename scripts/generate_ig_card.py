"""Render an Instagram-format (1080x1350, 4:5 portrait) quote card.

Adapted from scripts/generate-quote-card.py (the 1600x900 share card).
Same palette, same fonts, IG-safe proportions.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(__file__).resolve().parent / "fonts"

BG = (245, 241, 232)
CARD = (255, 255, 255)
BORDER = (26, 30, 58, 18)
RULE = (108, 184, 214)
INK = (26, 30, 58)
INK_MUTED = (128, 136, 168)
TAG = (128, 136, 168, 220)

W, H = 1080, 1350
PAD_OUT = 50
CARD_RADIUS = 22
CARD_PAD_X = 70
CARD_PAD_Y = 80
QUOTE_INDENT = 36
RULE_WIDTH = 4
TOP_RULE_HEIGHT = 6


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    words = text.split()
    lines, line = [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _smart_quotes(s: str) -> str:
    s = re.sub(r'"([^"]*)"', "“\\1”", s)
    s = s.replace("'", "’")
    return s


def _fit_quote(quote: str, draw, max_width: int, max_height: int):
    for size in (72, 64, 58, 52, 48, 44, 40, 36, 32):
        font = _font("CormorantGaramond-Italic.ttf", size)
        lines = _wrap(quote, font, max_width, draw)
        line_h = int(size * 1.32)
        if line_h * len(lines) <= max_height:
            return font, lines, line_h
    return font, lines, line_h


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.replace("www.", "")
        return host or ""
    except Exception:
        return ""


def render_ig(entry: dict, out_path) -> Path:
    out_path = Path(out_path)
    quote = _smart_quotes((entry.get("blockquote") or "").strip())
    name = entry.get("attribution") or entry.get("blockquote_source") or ""
    title = entry.get("attribution_title") or ""
    url = entry.get("source_url") or ""
    host = _domain(url)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    card_box = (PAD_OUT, PAD_OUT, W - PAD_OUT, H - PAD_OUT)
    draw.rounded_rectangle(card_box, radius=CARD_RADIUS, fill=CARD, outline=BORDER, width=1)

    draw.rectangle(
        (card_box[0] + 2, card_box[1] + 2, card_box[2] - 2, card_box[1] + TOP_RULE_HEIGHT + 2),
        fill=RULE,
    )

    cx0 = card_box[0] + CARD_PAD_X
    cx1 = card_box[2] - CARD_PAD_X
    cy0 = card_box[1] + CARD_PAD_Y + TOP_RULE_HEIGHT
    cy1 = card_box[3] - CARD_PAD_Y

    attr_h = 230
    quote_box_h = (cy1 - cy0) - attr_h

    quote_text_x = cx0 + QUOTE_INDENT
    quote_max_w = cx1 - quote_text_x
    font_q, lines, line_h = _fit_quote(quote, draw, quote_max_w, quote_box_h)
    total_q_h = line_h * len(lines)
    qy = cy0 + max(0, (quote_box_h - total_q_h) // 2)

    draw.rectangle((cx0, qy, cx0 + RULE_WIDTH, qy + total_q_h), fill=RULE)

    y = qy
    for line in lines:
        draw.text((quote_text_x, y), line, fill=INK, font=font_q)
        y += line_h

    ay = cy1 - attr_h + 30
    font_name = _font("DMSans-Bold.ttf", 34)
    font_title = _font("DMSans-Regular.ttf", 24)
    font_src = _font("DMSans-Regular.ttf", 22)

    draw.text((cx0, ay), name, fill=INK, font=font_name)
    ay += 46
    if title:
        for tl in _wrap(title, font_title, cx1 - cx0, draw)[:3]:
            draw.text((cx0, ay), tl, fill=INK_MUTED, font=font_title)
            ay += 32
    if host:
        ay += 12
        draw.text((cx0, ay), f"↗ {host}", fill=INK_MUTED, font=font_src)

    font_tag = _font("DMSans-Regular.ttf", 22)
    tag_text = "howisincorruptiblegoing.com"
    tag_w = draw.textlength(tag_text, font=font_tag)
    draw.text((cx1 - tag_w, cy1 - 28), tag_text, fill=TAG, font=font_tag)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: generate_ig_card.py <entry-json> [<out-png>]", file=sys.stderr)
        return 2
    entry_path = Path(argv[0])
    entry = json.loads(entry_path.read_text())
    entry_id = entry["id"]
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "public/images/ig-cards" / f"{entry_id}.png"
    p = render_ig(entry, out)
    print(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
