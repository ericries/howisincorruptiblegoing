"""Tests for quote-card type fitting.

Run: uv run --with pytest pytest scripts/test_generate_quote_card.py
"""
import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw

_spec = importlib.util.spec_from_file_location(
    "gen_quote_card", Path(__file__).resolve().parent / "generate-quote-card.py"
)
gqc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gqc)


def _fit(quote, max_width=1180, max_height=560):
    draw = ImageDraw.Draw(Image.new("RGB", (1600, 900)))
    font, lines, line_h = gqc.fit_quote(quote, draw, max_width, max_height)
    return font.size, lines


# --- Poster lane: a one-word blurb should be set large, not lost in whitespace ---

def test_single_word_fragment_is_set_large():
    size, lines = _fit("astounding")
    assert size > 62, f"one-word blurb rendered at {size}pt"
    assert lines == ["astounding"]


def test_short_phrase_is_set_large():
    size, _ = _fit("This is amazing")
    assert size > 62


# --- Attribution lines must be emoji-stripped too, not just the quote ---
# 2026-10-05: Mary Bonsor's LinkedIn headline contained "Parent of 2 👧🏻", which
# rendered as tofu boxes on the card. The quote text was stripped; the name and
# role lines were not.

def test_attribution_name_is_emoji_stripped():
    assert "🧸" not in gqc.strip_emoji("Abigail Frances 🧸☁️")
    assert gqc.strip_emoji("Abigail Frances 🧸☁️") == "Abigail Frances"


def test_attribution_role_is_emoji_stripped():
    role = "GC Relationships Director | Founder of Flex Legal | Parent of 2 👧🏻| Trustee"
    out = gqc.strip_emoji(role)
    assert "👧" not in out and "🏻" not in out
    assert "Parent of 2" in out and "Trustee" in out


def test_skin_tone_modifier_removed_with_its_base():
    """Fitzpatrick modifiers (U+1F3FB-FF) are separate codepoints — if the base
    emoji is stripped but the modifier is not, a lone tofu box remains."""
    for s in ["👧🏻", "👍🏽", "🤷🏼‍♀️", "🙏🏾"]:
        assert gqc.strip_emoji(f"a {s} b") == "a b", s


def test_variation_selector_and_zwj_removed():
    assert gqc.strip_emoji("ok ✌️ then") == "ok then"
    assert gqc.strip_emoji("x 👨‍👩‍👦 y") == "x y"


def test_plain_text_is_untouched():
    s = "GC Relationships Director | Founder of Flex Legal | NED"
    assert gqc.strip_emoji(s) == s


# --- Arrows are typography, not emoji. The fonts HAVE these glyphs (verified
# against the cmap of all four TTFs), so stripping them silently corrupted text:
# "0→1 product creator" was rendering as "01 product creator". ---

def test_typographic_arrows_survive():
    assert gqc.strip_emoji("0→1 product creator") == "0→1 product creator"
    assert gqc.strip_emoji("Build → Test → Learn") == "Build → Test → Learn"
    assert gqc.strip_emoji("Mission Hopeful → Mission Controlled") == \
        "Mission Hopeful → Mission Controlled"


def test_other_supported_punctuation_survives():
    for s in ["a ← b", "a ↔ b", "↗ linkedin.com", "Name · Role", "em — dash"]:
        assert gqc.strip_emoji(s) == s, s


def test_emoji_presentation_arrow_keeps_the_arrow_drops_the_selector():
    """↗️ is an arrow plus VARIATION SELECTOR-16. Keep the glyph the font has,
    drop the selector the font does not."""
    assert gqc.strip_emoji("see ↗️ here") == "see ↗ here"


def test_render_strips_emoji_from_both_attribution_lines():
    """The actual regression: strip_emoji worked, render() just never called it."""
    name, title = gqc.attribution_lines({
        "attribution": "Mary Bonsor 🎉",
        "attribution_title": "GC Relationships Director | Parent of 2 👧🏻| NED",
    })
    assert name == "Mary Bonsor"
    assert "👧" not in title and "🏻" not in title
    assert "Parent of 2" in title and "NED" in title


def test_attribution_falls_back_to_blockquote_source():
    name, _ = gqc.attribution_lines({"blockquote_source": "Someone on LinkedIn ✨"})
    assert name == "Someone on LinkedIn"


def test_attribution_handles_missing_fields():
    assert gqc.attribution_lines({}) == ("", "")
    assert gqc.attribution_lines({"attribution": None, "attribution_title": None}) == ("", "")


# --- Existing behaviour must not regress: normal quotes keep today's ladder ---

def test_full_sentence_quote_unchanged():
    size, _ = _fit(
        "Incorruptible is the best business book I have read in a decade, and I have "
        "read a great many of them over the years in this industry."
    )
    assert size <= 62


def test_long_quote_still_fits_inside_the_box():
    long_quote = (
        "I have been slowly chipping away at this book because its premise is something "
        "I have seen happen with my own eyes, and it is painful. It does not matter how "
        "great your company is or how smart you think you are; without the right legal "
        "guardrails to protect it, success will crush you."
    )
    size, lines = _fit(long_quote)
    assert size <= 62
    assert int(size * 1.35) * len(lines) <= 560
