"""Tests for the review bot's prompt-injection scan.

The bot runs in CI and blocks a PR, so a false positive here is as costly as a
miss: on 2026-10-20 a legitimate Persian-language review was rejected because
U+200C, which Persian orthography requires, was lumped in with the zero-width
characters that exist only to hide text.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_bot.validate_entries import detect_injection


def _reasons(**fields):
    return detect_injection(fields)


# --- orthography is not an attack -----------------------------------------------

def test_persian_zwnj_is_allowed():
    # "می‌کشد" / "می‌خواهیم" are spelled with U+200C. It marks a letter-form
    # boundary; dropping or rejecting it mangles the word.
    persian = "اریک ریس در کتاب Incorruptible یک مسئله مهم را پیش می‌کشد"
    assert _reasons(blockquote=persian) == []


def test_zwnj_run_is_still_padding():
    # Orthographic ZWNJ appears singly between letters. A run is hiding something.
    assert _reasons(blockquote="pad" + "‌" * 12 + "ding") != []


# --- the genuine hiding characters stay blocked ---------------------------------

def test_zero_width_space_is_blocked():
    assert _reasons(blockquote="Normal​text​with​hidden") != []


def test_zero_width_joiner_is_blocked():
    assert _reasons(blockquote="Normal‍text‍with‍hidden") != []


def test_word_joiner_is_blocked():
    assert _reasons(blockquote="Normal⁠text") != []


def test_bom_is_blocked():
    assert _reasons(blockquote="Normal﻿text") != []


def test_rtl_override_is_still_blocked_even_in_rtl_text():
    # Persian is right-to-left natively; it never needs an explicit override.
    assert _reasons(blockquote="اریک ریس ‮ در کتاب") != []
