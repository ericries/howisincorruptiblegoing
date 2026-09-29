"""Render a multi-page LinkedIn carousel PDF of AMA Q&As.

Output: 1080x1350 portrait, 10 pages, cream/navy/blue Incorruptible palette.
Page 1: cover. Pages 2-9: Q&A cards. Page 10: outro with links.

Usage:
    uv run --with pillow python scripts/generate_ama_carousel.py <out.pdf>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(__file__).resolve().parent / "fonts"

BG = (245, 241, 232)
CARD = (255, 255, 255)
BORDER = (26, 30, 58, 18)
RULE = (108, 184, 214)
INK = (26, 30, 58)
INK_MUTED = (128, 136, 168)
INK_LIGHT = (74, 78, 106)
LABEL = (140, 145, 170)
TAG = (128, 136, 168, 220)

W, H = 1080, 1350
PAD_OUT = 50
CARD_RADIUS = 22
CARD_PAD_X = 80
CARD_PAD_Y = 90
TOP_RULE_HEIGHT = 6


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit_answer(text: str, draw, max_width: int, max_height: int):
    for size in (62, 56, 50, 46, 42, 38, 34):
        font = _font("CormorantGaramond-Italic.ttf", size)
        lines = _wrap(text, font, max_width, draw)
        line_h = int(size * 1.32)
        if line_h * len(lines) <= max_height:
            return font, lines, line_h
    return font, lines, line_h


def _new_page() -> tuple[Image.Image, ImageDraw.ImageDraw, tuple]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    card_box = (PAD_OUT, PAD_OUT, W - PAD_OUT, H - PAD_OUT)
    draw.rounded_rectangle(card_box, radius=CARD_RADIUS, fill=CARD, outline=BORDER, width=1)
    draw.rectangle(
        (card_box[0] + 2, card_box[1] + 2, card_box[2] - 2, card_box[1] + TOP_RULE_HEIGHT + 2),
        fill=RULE,
    )
    return img, draw, card_box


def _watermark(draw, card_box, page_n: int, total: int) -> None:
    cx0, cy0, cx1, cy1 = card_box
    font = _font("DMSans-Regular.ttf", 20)
    tag_text = "howisincorruptiblegoing.com"
    tag_w = draw.textlength(tag_text, font=font)
    draw.text((cx1 - CARD_PAD_X - tag_w, cy1 - 60), tag_text, fill=TAG, font=font)

    page_text = f"{page_n} / {total}"
    draw.text((cx0 + CARD_PAD_X, cy1 - 60), page_text, fill=TAG, font=font)


def render_cover(out_path, total_pages: int) -> Image.Image:
    img, draw, (cx0, cy0, cx1, cy1) = _new_page()
    cx_l = cx0 + CARD_PAD_X
    cx_r = cx1 - CARD_PAD_X
    cy_t = cy0 + CARD_PAD_Y + TOP_RULE_HEIGHT
    cy_b = cy1 - CARD_PAD_Y

    label_font = _font("DMSans-Bold.ttf", 26)
    draw.text((cx_l, cy_t + 20), "LIVE AMA — 2026-06-10", fill=LABEL, font=label_font)

    title_font = _font("CormorantGaramond-Italic.ttf", 84)
    title = "What people are\nasking about\nIncorruptible."
    y = cy_t + 100
    for line in title.split("\n"):
        draw.text((cx_l, y), line, fill=INK, font=title_font)
        y += int(84 * 1.18)

    sub_font = _font("DMSans-Regular.ttf", 28)
    sub_lines = _wrap(
        "Highlights from today's Hacker News + Product Hunt AMAs — the questions cutting closest to what the book is actually about.",
        sub_font,
        cx_r - cx_l,
        draw,
    )
    y += 60
    for line in sub_lines:
        draw.text((cx_l, y), line, fill=INK_LIGHT, font=sub_font)
        y += 40

    name_font = _font("DMSans-Bold.ttf", 32)
    role_font = _font("DMSans-Regular.ttf", 24)
    draw.text((cx_l, cy_b - 130), "Eric Ries", fill=INK, font=name_font)
    draw.text(
        (cx_l, cy_b - 90),
        "Author, Incorruptible — Authors Equity, May 2026",
        fill=INK_MUTED,
        font=role_font,
    )

    swipe_font = _font("DMSans-Bold.ttf", 22)
    swipe = "SWIPE FOR THE QUESTIONS  →"
    draw.text((cx_l, cy_b - 30), swipe, fill=RULE, font=swipe_font)

    _watermark(draw, (cx0, cy0, cx1, cy1), 1, total_pages)
    return img


def render_qa(
    page_n: int,
    total_pages: int,
    asker_label: str,
    platform_tag: str,
    question: str,
    answer: str,
) -> Image.Image:
    img, draw, card_box = _new_page()
    cx0, cy0, cx1, cy1 = card_box
    cx_l = cx0 + CARD_PAD_X
    cx_r = cx1 - CARD_PAD_X
    cy_t = cy0 + CARD_PAD_Y + TOP_RULE_HEIGHT
    cy_b = cy1 - CARD_PAD_Y - 80

    inner_w = cx_r - cx_l

    label_font = _font("DMSans-Bold.ttf", 24)
    draw.text(
        (cx_l, cy_t),
        f"{platform_tag.upper()}  ·  {asker_label}",
        fill=LABEL,
        font=label_font,
    )

    q_font = _font("DMSans-Regular.ttf", 28)
    q_lines = _wrap(question, q_font, inner_w, draw)[:4]
    y = cy_t + 50
    for line in q_lines:
        draw.text((cx_l, y), line, fill=INK_LIGHT, font=q_font)
        y += 38

    y += 20
    draw.rectangle((cx_l, y, cx_r, y + 2), fill=RULE)
    y += 36

    answer_max_h = cy_b - y - 80
    a_font, a_lines, line_h = _fit_answer(f"“{answer}”", draw, inner_w, answer_max_h)
    for line in a_lines:
        draw.text((cx_l, y), line, fill=INK, font=a_font)
        y += line_h

    attr_font = _font("DMSans-Bold.ttf", 26)
    draw.text((cx_l, cy_b - 30), "— Eric Ries", fill=INK, font=attr_font)

    _watermark(draw, card_box, page_n, total_pages)
    return img


def render_outro(total_pages: int) -> Image.Image:
    img, draw, card_box = _new_page()
    cx0, cy0, cx1, cy1 = card_box
    cx_l = cx0 + CARD_PAD_X
    cx_r = cx1 - CARD_PAD_X
    cy_t = cy0 + CARD_PAD_Y + TOP_RULE_HEIGHT
    cy_b = cy1 - CARD_PAD_Y

    label_font = _font("DMSans-Bold.ttf", 26)
    draw.text((cx_l, cy_t + 20), "MORE QUESTIONS, MORE ANSWERS", fill=LABEL, font=label_font)

    title_font = _font("CormorantGaramond-Italic.ttf", 72)
    title_lines = ["The AMAs are still", "running. Drop in:"]
    y = cy_t + 90
    for line in title_lines:
        draw.text((cx_l, y), line, fill=INK, font=title_font)
        y += int(72 * 1.2)

    link_label_font = _font("DMSans-Bold.ttf", 26)
    link_font = _font("DMSans-Regular.ttf", 24)

    y += 60
    draw.text((cx_l, y), "HACKER NEWS", fill=LABEL, font=link_label_font)
    draw.text((cx_l, y + 36), "news.ycombinator.com/item?id=48477135", fill=INK, font=link_font)

    y += 110
    draw.text((cx_l, y), "PRODUCT HUNT", fill=LABEL, font=link_label_font)
    draw.text(
        (cx_l, y + 36),
        "producthunt.com/p/incorruptible-by-eric-ries",
        fill=INK,
        font=link_font,
    )

    y += 110
    draw.text((cx_l, y), "GET THE BOOK", fill=LABEL, font=link_label_font)
    draw.text((cx_l, y + 36), "incorruptible.co", fill=INK, font=link_font)

    name_font = _font("DMSans-Bold.ttf", 30)
    role_font = _font("DMSans-Regular.ttf", 22)
    draw.text((cx_l, cy_b - 90), "Eric Ries", fill=INK, font=name_font)
    draw.text((cx_l, cy_b - 54), "Incorruptible — Authors Equity, May 2026", fill=INK_MUTED, font=role_font)

    _watermark(draw, card_box, total_pages, total_pages)
    return img


QA_ITEMS = [
    {
        "asker": "@k2xl",
        "platform": "Hacker News",
        "question": "Why did you decide to write this book?",
        "answer": "I'm sick and tired of helping people become rich and miserable, creating great companies only for them to be destroyed out of the gates. What is the point of all this carnage? Who is it for?",
    },
    {
        "asker": "@ixxie",
        "platform": "Hacker News",
        "question": "I'm curious if you think cooperative businesses leveraging non-voting preferred shares, community shares and other coop investment instruments are more resilient against this type of corruption.",
        "answer": "I hate the word 'exit' altogether. It's only the investors who are leaving Middle Earth; the rest of us are still try to make this thing work.",
    },
    {
        "asker": "@fapi1974",
        "platform": "Hacker News",
        "question": "How is corruption different from your concept of financial gravity?",
        "answer": "If you ask an engineer 'why did it collapse' you'll be annoyed if they say 'gravity' even though that is technically correct.",
    },
    {
        "asker": "@dani_mashael",
        "platform": "Product Hunt",
        "question": "At what company size does the governance fortress become necessary versus just founder values being enough?",
        "answer": "It's always too early until it's too late.",
    },
    {
        "asker": "@mrdrqr",
        "platform": "Hacker News",
        "question": "What parts of The Lean Startup would you update for the AI era?",
        "answer": "None of them, really.",
    },
    {
        "asker": "@stphnmrrs",
        "platform": "Product Hunt",
        "question": "Is there a point in time where the scales tipped to the short-termism?",
        "answer": "This shift is, fortunately, young enough that it's still quite easily reversible, if we will it.",
    },
    {
        "asker": "@hmokiguess",
        "platform": "Hacker News",
        "question": "I feel like the system is designed so that VCs keep winning and founders rarely get the exit they deserve. What is your take on that?",
        "answer": "One study I cite in the book found that something like 80% of founders of venture-backed companies will no longer be CEO even three years after an IPO.",
    },
    {
        "asker": "@andsoitis",
        "platform": "Hacker News",
        "question": "What do you think are the hallmarks of a great company mission?",
        "answer": "I will not help you wordsmith your mission statement. I frankly don't think it matters.",
    },
]


def build(out_path: Path) -> Path:
    total = len(QA_ITEMS) + 2
    pages = [render_cover(out_path, total)]
    for i, item in enumerate(QA_ITEMS, start=2):
        pages.append(
            render_qa(
                page_n=i,
                total_pages=total,
                asker_label=item["asker"],
                platform_tag=item["platform"],
                question=item["question"],
                answer=item["answer"],
            )
        )
    pages.append(render_outro(total))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out_path, "PDF", save_all=True, append_images=pages[1:], resolution=144.0)
    return out_path


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        out = ROOT / "public" / "documents" / "ama-carousel-2026-06-10.pdf"
    else:
        out = Path(argv[0])
    p = build(out)
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
