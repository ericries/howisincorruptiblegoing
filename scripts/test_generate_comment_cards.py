"""Tests for the comment-card gate and filenames.

Both bugs here surfaced on 2026-10-20, the day the archive gained Twitter/X.

  - The gate required the quote itself to name the book or Eric. That is wrong
    for a reply: Kevin Payne's "Metrics outlive principles. Once the dashboard
    rewards extraction, the people who remember why the company worked stop
    getting promoted" is a reply to Eric's own post and never needs to say so.
    Three of eight new records were rejected as "no-book-anchor".
  - Card filenames are <date>-<name-slug>.png, so a person with more than one
    kept comment in a day silently overwrites their own card. Kevin Payne had
    four and Danny two; six renders produced three files. This predates Twitter
    — it would have hit any LinkedIn commenter quoted twice in a day.
"""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "generate_comment_cards",
    Path(__file__).resolve().parent / "generate-comment-cards.py",
)
gcc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gcc)


def record(**kw):
    base = {
        "pull_quote": "Metrics outlive principles",
        "full_text": ("Metrics outlive principles. Once the dashboard rewards extraction, "
                      "the people who remember why the company worked stop getting promoted."),
        "superlative_matches": ["<llm>"],
        "platform": "twitter",
        "author": {"name": "Kevin Payne", "headline": "GTM Engineer at LawVu"},
        "permalink": "https://x.com/kevintpayne/status/2112680802366697543",
        "identifier": "tweet:2112680802366697543",
        "likes": 0,
    }
    base.update(kw)
    return base


# --- the anchor gate ----------------------------------------------------------------

def test_a_reply_to_eric_does_not_need_to_name_the_book():
    ok, why = gcc.card_worthy(record())
    assert ok, why


def test_a_quote_that_names_the_book_still_passes():
    ok, why = gcc.card_worthy(record(
        pull_quote="Incorruptible is the best business book I have read in years",
        full_text="Incorruptible is the best business book I have read in years."))
    assert ok, why


def test_an_unanchored_quote_with_no_reply_context_is_still_rejected():
    # A long musing that never touches the book and is not a reply stays out.
    ok, why = gcc.card_worthy(record(
        platform="linkedin", permalink="https://www.linkedin.com/posts/x",
        parent_post=None,
        pull_quote="The weather in Dallas was unusually mild for October this year",
        full_text="The weather in Dallas was unusually mild for October this year."))
    assert not ok
    assert "anchor" in why


# --- filenames ----------------------------------------------------------------------

def test_two_quotes_from_the_same_person_on_one_day_get_different_filenames():
    a = gcc.card_filename("2026-10-20", record())
    b = gcc.card_filename("2026-10-20", record(
        identifier="tweet:2112680802366697544",
        pull_quote="Governance is cheapest when there is little to unwind"))
    assert a != b, "same-day cards for one person must not overwrite each other"
    assert a.startswith("2026-10-20-kevin-payne")
    assert b.startswith("2026-10-20-kevin-payne")
    assert a.endswith(".png") and b.endswith(".png")


def test_the_filename_is_stable_for_the_same_record():
    r = record()
    assert gcc.card_filename("2026-10-20", r) == gcc.card_filename("2026-10-20", r)


def test_a_single_quote_keeps_the_plain_name_filename():
    # Don't churn the 40 days of existing cards: one comment from a person on a
    # day should still render as <date>-<name>.png.
    assert gcc.card_filename("2026-10-20", record(), only_one=True) == "2026-10-20-kevin-payne.png"
