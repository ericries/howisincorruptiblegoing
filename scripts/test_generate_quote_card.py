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
