"""Tests for lib.source_texts — full-source capture for published entries.

The site publishes a `blockquote` excerpt. These tests pin the guarantee that the
*complete* source text is kept locally, so we can re-read or re-quote later
without re-scraping.

Run: uv run --with pytest pytest scripts/test_source_texts.py -v
"""
import json

import pytest

from lib import source_texts


@pytest.fixture(autouse=True)
def tmp_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(source_texts, "ARCHIVE_DIR", tmp_path / "source-texts")
    return tmp_path / "source-texts"


LONG = (
    "One of the defining business books of our century.\n\n"
    + "Eric Ries' INCORRUPTIBLE is without a doubt one of the top books of this century. "
    * 40
)


# === capture stores the whole thing ===

def test_capture_stores_full_text_verbatim():
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert source_texts.load("e1")["full_text"] == LONG


def test_capture_does_not_truncate_long_text():
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert len(source_texts.load("e1")["full_text"]) == len(LONG)


def test_capture_preserves_newlines_and_unicode():
    text = "Line one\n\nLine two — with an em dash, curly ’quote’ and emoji 📘"
    source_texts.capture("e1", source_url="https://x.test/1", full_text=text)
    assert source_texts.load("e1")["full_text"] == text


def test_capture_records_provenance():
    source_texts.capture(
        "e1", source_url="https://x.test/1", full_text="hello",
        author="Art Moore", platform="linkedin",
    )
    rec = source_texts.load("e1")
    assert rec["entry_id"] == "e1"
    assert rec["source_url"] == "https://x.test/1"
    assert rec["author"] == "Art Moore"
    assert rec["platform"] == "linkedin"
    assert rec["captured_at"].endswith("Z")


# === idempotence and the never-shrink rule ===

def test_recapturing_identical_text_is_idempotent(tmp_archive):
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    first = (tmp_archive / "e1.json").read_text()
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert (tmp_archive / "e1.json").read_text() == first


def test_capture_never_replaces_a_longer_text_with_a_shorter_one():
    """A later scan that only sees the published excerpt must not clobber the
    full text we already hold."""
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    source_texts.capture("e1", source_url="https://x.test/1", full_text="short excerpt")
    assert source_texts.load("e1")["full_text"] == LONG


def test_capture_upgrades_to_a_longer_text():
    source_texts.capture("e1", source_url="https://x.test/1", full_text="short excerpt")
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert source_texts.load("e1")["full_text"] == LONG


def test_capture_keeps_earliest_captured_at():
    source_texts.capture("e1", source_url="https://x.test/1", full_text="a",
                         captured_at="2026-01-01T00:00:00Z")
    source_texts.capture("e1", source_url="https://x.test/1", full_text="a longer one",
                         captured_at="2026-06-01T00:00:00Z")
    assert source_texts.load("e1")["captured_at"] == "2026-01-01T00:00:00Z"


def test_capture_rejects_empty_text():
    with pytest.raises(ValueError):
        source_texts.capture("e1", source_url="https://x.test/1", full_text="   ")


def test_entry_id_with_slash_is_rejected():
    """Entry ids become filenames; a path separator must not escape the dir."""
    with pytest.raises(ValueError):
        source_texts.capture("../escape", source_url="https://x.test/1", full_text="hi")


# === reading back ===

def test_load_returns_none_for_unknown_entry():
    assert source_texts.load("nope") is None


def test_has_returns_false_then_true():
    assert source_texts.has("e1") is False
    source_texts.capture("e1", source_url="https://x.test/1", full_text="hi")
    assert source_texts.has("e1") is True


# === coverage reporting ===

def test_missing_lists_only_uncaptured_entries():
    source_texts.capture("e1", source_url="https://x.test/1", full_text="hi")
    entries = [{"id": "e1"}, {"id": "e2"}, {"id": "e3"}]
    assert source_texts.missing(entries) == ["e2", "e3"]


def test_missing_is_empty_when_all_captured():
    source_texts.capture("e1", source_url="https://x.test/1", full_text="hi")
    assert source_texts.missing([{"id": "e1"}]) == []


# === the blockquote must actually be findable in what we stored ===

def test_contains_blockquote_true_when_excerpt_present():
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert source_texts.contains_blockquote("e1", "top books of this century") is True


def test_contains_blockquote_false_when_excerpt_absent():
    source_texts.capture("e1", source_url="https://x.test/1", full_text=LONG)
    assert source_texts.contains_blockquote("e1", "never appears anywhere") is False


def test_contains_blockquote_ignores_whitespace_differences():
    source_texts.capture("e1", source_url="https://x.test/1",
                         full_text="the quick\n\nbrown   fox")
    assert source_texts.contains_blockquote("e1", "quick brown fox") is True
