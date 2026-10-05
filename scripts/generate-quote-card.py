#!/usr/bin/env python3
"""Render a quote card PNG for a timeline entry.

Usage: python3 scripts/generate-quote-card.py <entry-json> [<out-png>]

Produces a 1600x900 share-friendly card that matches the site's timeline
card style (cream background, white card, blue rules, serif quote,
DM Sans attribution) with a howisincorruptiblegoing.com tag at the
bottom. Intended for entries that lack a native image — the generated
PNG goes into public/images/cards/<entry-id>.png and is set as the
entry's `image` field.
"""
import json, sys, re
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(__file__).resolve().parent / "fonts"

# Palette — matches src/styles/global.css
BG          = (245, 241, 232)   # cream — same as bestseller strip
CARD        = (255, 255, 255)
BORDER      = (26, 30, 58, 18)  # very subtle navy hairline
RULE_TOP    = (108, 184, 214)   # --color-blue
RULE_QUOTE  = (108, 184, 214)
INK         = (26, 30, 58)      # --color-navy / --color-text
INK_MUTED   = (128, 136, 168)   # --color-text-muted
INK_LIGHT   = (74, 78, 106)     # --color-text-light
TAG         = (128, 136, 168, 200)

W, H = 1600, 900
PAD_OUT = 60              # outer breathing room
CARD_RADIUS = 18
CARD_PAD_X = 90
CARD_PAD_Y = 70
QUOTE_INDENT = 50         # space after the left rule
RULE_WIDTH = 4
TOP_RULE_HEIGHT = 5

def load_font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)

def wrap(text, font, max_width, draw):
    """Greedy word wrap to max_width."""
    words = text.split()
    lines, line = [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line: lines.append(line)
            line = w
    if line: lines.append(line)
    return lines

def domain_of(url):
    try:
        host = urlparse(url).netloc.replace("www.", "")
        return host or ""
    except Exception:
        return ""

# Codepoints the bundled faces cannot draw, which would render as tofu (□).
#
# The arrows block (U+2190-21FF) is deliberately NOT stripped wholesale: all four
# TTFs carry → ← ↔ ↗ (verified against their cmap tables), and blanket-stripping
# turned "0→1 product creator" into "01 product creator" and "Build → Test →
# Learn" into "Build Test Learn". Only the arrows the fonts genuinely lack are
# listed. Variation selectors and ZWJ are always dropped — they are invisible
# modifiers, so removing them leaves the base glyph the font does have (↗️ → ↗).
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"      # pictographs, supplemental symbols, skin tones
    "\U00002600-\U000027BF"      # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"      # regional indicators (flags)
    "\U00002B00-\U00002BFF"      # misc symbols and arrows (⬆ ⭐ …)
    "\U00002300-\U000023FF"      # misc technical (⌚ ⏰ …)
    "\U000021A0-\U000021FF"      # arrows the fonts lack (⇒ ⇐ …); → ← ↔ ↗ kept
    "\U0000FE00-\U0000FE0F"      # variation selectors
    "\U0000200D"                 # zero-width joiner
    "\U0000203C\U00002049"       # ‼ ⁉
    "]"
)


def strip_emoji(s):
    """Remove glyphs the bundled fonts cannot draw (they render as tofu □) and
    clean up the leftover spacing. Typographic punctuation the fonts DO carry
    — arrows, middot, em dash — is preserved."""
    s = _EMOJI.sub("", s)
    s = re.sub(r"\s+([,.;:!?…])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def smart_quotes(s):
    """Replace straight quotes with typographic curly quotes for serif rendering."""
    s = strip_emoji(s)
    s = re.sub(r'"([^"]*)"', "“\\1”", s)
    s = s.replace("'", "’")
    return s

# Normal ladder for sentence-length quotes.
SIZES = (62, 56, 50, 46, 42, 38, 34, 30, 27, 24)
# Poster ladder, tried first for blurb-length fragments only ("astounding").
# At 62pt a single word is swallowed by the card; a blurb wants display type.
POSTER_SIZES = (150, 128, 110, 94, 80, 70)
POSTER_MAX_CHARS = 48


def fit_quote(quote, draw, max_width, max_height):
    """Try descending font sizes until the wrapped quote fits.
    If even the smallest size overflows, truncate the trailing lines and add an
    ellipsis so the quote never collides with the attribution block. Trailing
    truncation of a contiguous span is acceptable (the full quote is at source)."""
    ladder = SIZES
    if len(quote.strip()) <= POSTER_MAX_CHARS:
        ladder = POSTER_SIZES + SIZES
    for size in ladder:
        font = load_font("CormorantGaramond-Italic.ttf", size)
        lines = wrap(quote, font, max_width, draw)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_height:
            return font, lines, line_h
    # Smallest size still overflows -> keep only the lines that fit + ellipsis
    max_lines = max(1, max_height // line_h)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1].rstrip()
        if not last.endswith(("…", ".", "!", "?", "”", '"')):
            last = last.rstrip(",;:—- ") + "…"
        else:
            last = last + "…" if not last.endswith("…") else last
        lines[-1] = last
    return font, lines, line_h

def attribution_lines(d: dict) -> tuple[str, str]:
    """Name and role for the card footer, emoji-stripped.

    The DM Sans faces have no emoji glyphs, so anything left here renders as a
    tofu box. LinkedIn headlines are full of them — "Parent of 2 👧🏻" shipped as
    "Parent of 2 □□" on 2026-10-05 because only the quote was being stripped.
    """
    name = d.get("attribution") or d.get("blockquote_source", "") or ""
    title = d.get("attribution_title") or ""
    return strip_emoji(name), strip_emoji(title)


def render(entry_path: Path, out_path: Path):
    d = json.loads(entry_path.read_text())
    quote = smart_quotes(d.get("blockquote", "")).strip()
    name, title = attribution_lines(d)
    url = d.get("source_url") or ""
    host = domain_of(url)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # Outer card
    card_box = (PAD_OUT, PAD_OUT, W - PAD_OUT, H - PAD_OUT)
    draw.rounded_rectangle(card_box, radius=CARD_RADIUS, fill=CARD, outline=BORDER, width=1)

    # Top rule (just inside the rounded top edge)
    draw.rectangle(
        (card_box[0] + 2, card_box[1] + 2, card_box[2] - 2, card_box[1] + TOP_RULE_HEIGHT + 2),
        fill=RULE_TOP,
    )

    # Layout zones inside the card
    cx0 = card_box[0] + CARD_PAD_X
    cx1 = card_box[2] - CARD_PAD_X
    cy0 = card_box[1] + CARD_PAD_Y + TOP_RULE_HEIGHT
    cy1 = card_box[3] - CARD_PAD_Y

    # Attribution block reserves the bottom ~210px
    attr_h = 210
    quote_box_h = (cy1 - cy0) - attr_h

    # Render quote (fit to box)
    quote_text_x = cx0 + QUOTE_INDENT
    quote_max_w = cx1 - quote_text_x
    font_q, lines, line_h = fit_quote(quote, draw, quote_max_w, quote_box_h)
    total_q_h = line_h * len(lines)
    # Vertically center the quote within its box
    qy = cy0 + max(0, (quote_box_h - total_q_h) // 2)

    # Left blue rule next to the quote — only as tall as the quote itself
    rule_y0 = qy
    rule_y1 = qy + total_q_h
    draw.rectangle((cx0, rule_y0, cx0 + RULE_WIDTH, rule_y1), fill=RULE_QUOTE)

    # Draw quote lines
    for line in lines:
        draw.text((quote_text_x, qy), line, fill=INK, font=font_q)
        qy += line_h

    # Attribution: name + title + source link
    ay = cy1 - attr_h + 30
    font_name = load_font("DMSans-Bold.ttf", 30)
    font_title = load_font("DMSans-Regular.ttf", 22)
    font_src = load_font("DMSans-Regular.ttf", 20)
    draw.text((cx0, ay), name, fill=INK, font=font_name)
    ay += 40
    if title:
        # Wrap title if long
        title_lines = wrap(title, font_title, cx1 - cx0, draw)
        for tl in title_lines[:2]:  # cap at 2 lines
            draw.text((cx0, ay), tl, fill=INK_MUTED, font=font_title)
            ay += 30
    if host:
        ay += 14
        # Small arrow + domain
        draw.text((cx0, ay), f"↗ {host}", fill=INK_MUTED, font=font_src)

    # howisincorruptiblegoing.com tag at bottom right
    font_tag = load_font("DMSans-Regular.ttf", 18)
    tag_text = "howisincorruptiblegoing.com"
    tag_w = draw.textlength(tag_text, font=font_tag)
    draw.text(
        (cx1 - tag_w, cy1 - 22),
        tag_text,
        fill=TAG,
        font=font_tag,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path

def main():
    if len(sys.argv) < 2:
        print("usage: generate-quote-card.py <entry-json> [<out-png>]")
        sys.exit(2)
    entry_path = Path(sys.argv[1])
    if not entry_path.exists():
        print(f"entry not found: {entry_path}")
        sys.exit(1)
    entry_id = json.loads(entry_path.read_text())["id"]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "public/images/cards" / f"{entry_id}.png"
    p = render(entry_path, out_path)
    print(p.relative_to(ROOT))

if __name__ == "__main__":
    main()
