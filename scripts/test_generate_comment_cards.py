"""Tests for the comment-card selection gates.

Run: uv run --with pytest pytest scripts/test_generate_comment_cards.py
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "gen_comment_cards", Path(__file__).resolve().parent / "generate-comment-cards.py"
)
gcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gcc)


def rec(pull_quote, *, llm=True, text=None, **extra):
    r = {
        "pull_quote": pull_quote,
        "text": text if text is not None else pull_quote,
        "superlative_matches": ["<llm>"] if llm else ["amazing"],
    }
    r.update(extra)
    return r


# --- Fragment lane: poster-style superlatives (2026-10-03, Eric's direction) ---
# "keep comments in the archive like 'astounding' (just that one word is enough,
# we dont need the rest for things like movie posters)"

def test_single_word_superlative_passes():
    ok, reason = gcc._passes_selection_gates(
        rec("astounding", text="Eric Ries astounding. What do you like best about your own book?")
    )
    assert ok, reason


def test_short_pronoun_led_superlative_passes():
    ok, reason = gcc._passes_selection_gates(rec("This is amazing", text="This is amazing Charlotte! 👏"))
    assert ok, reason


def test_short_phrase_without_book_anchor_passes():
    ok, reason = gcc._passes_selection_gates(
        rec("a worthy path toward building bigger",
            text="I had the same reaction after years of preferred micro/solo enterprise, "
                 "I can see a worthy path toward building bigger and preserving better.")
    )
    assert ok, reason


def test_pull_quote_is_used_verbatim_even_when_short():
    """A short pull_quote must not fall through to the full comment text."""
    assert gcc._substantive_text(
        rec("astounding", text="Eric Ries astounding. What do you like best about your own book?")
    ) == "astounding"


# --- The fragment lane is narrow: it must not become a general bypass ---

def test_regex_matched_fragment_still_rejected():
    """Only Claude-verified records get the fragment lane; regex matches don't."""
    ok, reason = gcc._passes_selection_gates(rec("astounding", llm=False))
    assert not ok
    assert "too-short" in reason


def test_medium_length_context_dependent_quote_still_rejected():
    ok, reason = gcc._passes_selection_gates(
        rec("It raises such a powerful question about what happens when the pressure is high")
    )
    assert not ok
    assert reason in ("no-book-anchor",) or "leading-pronoun" in reason


def test_already_have_still_wins_over_fragment_lane():
    ok, reason = gcc._passes_selection_gates(rec("astounding", already_have=True))
    assert not ok
    assert reason == "already_have"


def test_empty_quote_rejected():
    ok, reason = gcc._passes_selection_gates(rec("", text=""))
    assert not ok
    assert reason == "empty"


# --- Existing behaviour must not regress ---

def test_anchored_full_quote_passes():
    ok, reason = gcc._passes_selection_gates(
        rec("Incorruptible is the best business book I have read in a decade, full stop.")
    )
    assert ok, reason
