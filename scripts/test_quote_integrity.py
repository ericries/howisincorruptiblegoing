"""Check blockquotes against the source text we already captured.

Measured on 2026-10-28, the quote verifiers were checking almost nothing:

  - `verify-quotes.ts` skipped any entry with `verified: false`. Nothing has set
    that field true since June 2026, so it skipped 725 of 871 entries and
    verified 25 — 2.9% — while exiting 0.
  - `review_bot/verify_quotes.py` (the one that gates merges) has no such skip,
    but `fetch_page` returns None on any exception and None means WARN+continue.
    62% of entries cite LinkedIn or X, which no anonymous fetch can read, so
    those merge warned-but-unchecked every time.

Both were trying to re-acquire evidence the repo already holds:
`data/archive/source-texts/<entry-id>.json` carries the entire captured post or
review for 263 entries, 156 of them behind auth walls. Verifying against that
costs nothing, needs no network, and checks exactly the entries a fetch cannot.

The two postmortems this guards against are a fabricated blockquote
(2026-04-12) and a composited one that survived three months with half the
sentence belonging to Brian Chesky.
"""

from __future__ import annotations

import json

import pytest

from quote_integrity import (
    Verdict,
    check_entry,
    coverage,
    load_source_text,
    match_quote,
)


# --- matching ------------------------------------------------------------------------

def test_exact_match_is_exact():
    assert match_quote("the dashboard rewards extraction",
                       "Once the dashboard rewards extraction, people leave.") is Verdict.EXACT


def test_absent_quote_is_absent():
    assert match_quote("a sentence nobody wrote",
                       "Some entirely different text.") is Verdict.ABSENT


def test_smart_quotes_are_a_normalised_match_not_an_exact_one():
    """Byte-level drift still matters — Eric has asked for apostrophes to match.

    It is not a failure, but it must not be reported as clean either: the
    entry's stored text has diverged from the source and someone retyped it.
    """
    assert match_quote("it doesn't scale", "we found it doesn’t scale") is Verdict.NORMALISED


def test_em_dash_variation_is_normalised():
    assert match_quote("growth -- at any cost",
                       "growth — at any cost") is Verdict.NORMALISED


def test_collapsed_whitespace_is_normalised():
    """The 2026-10-24 Bob Sutton double-space repair, as a matcher case."""
    assert match_quote("you are Inexhaustible!",
                       "Bob said you are  Inexhaustible! today") is Verdict.NORMALISED


def test_partial_match_is_its_own_verdict():
    """A long quote whose opening appears but whose whole does not.

    This is the composited-quote signature and the single most important case
    in this module. The old verifier called it a warning and exited 0.
    """
    quote = ("Metrics outlive principles and the company forgets why it worked "
             "and then everyone leaves for somewhere better")
    page = "Metrics outlive principles and the company forgets why it worked. Full stop."
    assert match_quote(quote, page) is Verdict.PARTIAL


def test_short_quote_that_is_absent_is_not_called_partial():
    """A fragment shorter than the partial window must not score a false partial."""
    assert match_quote("astounding", "nothing like it here") is Verdict.ABSENT


def test_empty_source_text_is_unverifiable_not_absent():
    """No evidence is not the same as contradicting evidence."""
    assert match_quote("anything", "") is Verdict.NO_SOURCE


def test_empty_quote_is_unverifiable():
    assert match_quote("", "some text") is Verdict.NO_SOURCE


# --- entry-level checking -------------------------------------------------------------

def test_check_entry_uses_the_archived_source_text(tmp_path):
    (tmp_path / "e1.json").write_text(json.dumps(
        {"entry_id": "e1", "full_text": "He said the ratchet only turns one way."}))
    entry = {"id": "e1", "blockquote": "the ratchet only turns one way"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.EXACT


def test_check_entry_reports_no_source_when_nothing_archived(tmp_path):
    entry = {"id": "missing", "blockquote": "whatever"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.NO_SOURCE


def test_check_entry_surfaces_a_fabricated_quote(tmp_path):
    (tmp_path / "e2.json").write_text(json.dumps(
        {"entry_id": "e2", "full_text": "A completely unrelated post about gardening."}))
    entry = {"id": "e2", "blockquote": "Incorruptible changed how I think about governance"}
    r = check_entry(entry, archive_dir=tmp_path)
    assert r.verdict is Verdict.ABSENT
    assert r.entry_id == "e2"


def test_check_entry_tolerates_a_corrupt_archive_file(tmp_path):
    (tmp_path / "e3.json").write_text("{not json")
    assert check_entry({"id": "e3", "blockquote": "x"},
                       archive_dir=tmp_path).verdict is Verdict.NO_SOURCE


def test_load_source_text_returns_none_for_missing(tmp_path):
    assert load_source_text("nope", tmp_path) is None


# --- coverage, so decay is loud --------------------------------------------------------

def test_coverage_counts_only_what_was_actually_checked():
    results = [
        Verdict.EXACT, Verdict.EXACT, Verdict.NORMALISED,
        Verdict.NO_SOURCE, Verdict.NO_SOURCE,
    ]
    c = coverage(results)
    assert c["checked"] == 3
    assert c["total"] == 5
    assert c["unverifiable"] == 2


def test_coverage_counts_failures_as_checked():
    """A quote proven wrong IS a verification — the strongest kind."""
    c = coverage([Verdict.ABSENT, Verdict.PARTIAL, Verdict.NO_SOURCE])
    assert c["checked"] == 2
    assert c["failures"] == 2


def test_coverage_of_an_empty_set_is_not_a_division_by_zero():
    c = coverage([])
    assert c["checked"] == 0 and c["total"] == 0
    assert c["fraction"] == 0.0


def test_coverage_fraction():
    c = coverage([Verdict.EXACT, Verdict.NO_SOURCE, Verdict.EXACT, Verdict.EXACT])
    assert c["fraction"] == pytest.approx(0.75)


# --- the capture must be of the document the entry cites ------------------------------

def test_absence_in_a_different_document_is_not_refutation(tmp_path):
    """Found by running the checker: it reported 83 failures, mostly bogus.

    `data/archive/source-texts/<id>.json` is keyed by entry id, but the text it
    holds is sometimes a RELATED url — the X post announcing an article rather
    than the article, or a reaction comment rather than the post. Scoring
    "quote not in this text" as ABSENT then accuses a sound entry of being
    fabricated. An alarm that cries wolf 83 times is one nobody reads.
    """
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e",
        "source_url": "https://x.com/ItamarGilad/status/2115051657482416148",
        "full_text": "my biggest influences, so it was a great pleasure"}))
    entry = {"id": "e",
             "source_url": "https://itamargilad.com/eric-ries-incorruptible/",
             "blockquote": "the total cost of taking a wrong turn goes way up"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.SOURCE_MISMATCH


def test_absence_in_the_cited_document_is_still_a_failure(tmp_path):
    """The guard must not become a blanket excuse — matching urls still bite."""
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e",
        "source_url": "https://example.com/post",
        "full_text": "An article about something else entirely."}))
    entry = {"id": "e", "source_url": "https://example.com/post",
             "blockquote": "a quote that was never written here at all"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.ABSENT


def test_a_hit_counts_even_when_the_capture_url_differs(tmp_path):
    """Positive evidence is positive wherever it is found.

    If the words are demonstrably in a captured document, the quote is real —
    the url bookkeeping does not make it less real.
    """
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e", "source_url": "https://x.com/someone/status/1",
        "full_text": "He wrote: the ratchet only turns one way."}))
    entry = {"id": "e", "source_url": "https://example.com/article",
             "blockquote": "the ratchet only turns one way"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.EXACT


def test_url_comparison_ignores_scheme_www_and_trailing_slash(tmp_path):
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e", "source_url": "http://www.example.com/post/",
        "full_text": "nothing relevant"}))
    entry = {"id": "e", "source_url": "https://example.com/post",
             "blockquote": "a quote that is definitely not present here"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.ABSENT


def test_capture_with_no_url_recorded_is_compared_anyway(tmp_path):
    """Older captures predate the source_url field; absent means unknown, and
    unknown must not silently excuse a miss on the only evidence we have."""
    (tmp_path / "e.json").write_text(json.dumps(
        {"entry_id": "e", "full_text": "unrelated text"}))
    entry = {"id": "e", "source_url": "https://example.com/x",
             "blockquote": "a quote that is definitely not present here"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.ABSENT


def test_source_mismatch_counts_as_unverifiable_not_checked():
    c = coverage([Verdict.SOURCE_MISMATCH, Verdict.EXACT])
    assert c["checked"] == 1
    assert c["unverifiable"] == 1
    assert c["failures"] == 0


# --- a transcript cannot refute a quote taken from the page ---------------------------

def test_transcript_capture_that_misses_is_not_a_failure(tmp_path):
    """The 69 "failures" on first run were all transcripts, and all legitimate.

    A podcast or video entry has TWO bodies of text at one url: the spoken
    audio, and the written description/show notes. The scanner captures the
    transcript. Blockquotes are often pulled from the written blurb — "Eric
    shares powerful stories from companies like Costco, Cloudflare and
    Anthropic" is episode copy, not something anyone said aloud.

    Judging written copy against a transcript is a category error. It can
    confirm (if the words were spoken, they are in there) but it can never
    refute, because the document that would contain the quote was never
    captured.
    """
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e", "platform": "transcript",
        "source_url": "https://example.com/ep1",
        "full_text": "um so yeah i think governance really matters a lot"}))
    entry = {"id": "e", "source_url": "https://example.com/ep1",
             "blockquote": "Eric shares powerful stories from companies like Costco"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.MEDIUM_MISMATCH


def test_transcript_capture_that_matches_still_verifies(tmp_path):
    """Confirmation still works — the relaxation is one-directional."""
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e", "platform": "transcript",
        "source_url": "https://example.com/ep1",
        "full_text": "i think governance really matters a lot"}))
    entry = {"id": "e", "source_url": "https://example.com/ep1",
             "blockquote": "governance really matters"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.EXACT


def test_a_non_transcript_capture_still_refutes(tmp_path):
    """A captured LinkedIn post IS the document, so a miss there is real."""
    (tmp_path / "e.json").write_text(json.dumps({
        "entry_id": "e", "platform": "linkedin",
        "source_url": "https://example.com/p",
        "full_text": "An ordinary post about something else."}))
    entry = {"id": "e", "source_url": "https://example.com/p",
             "blockquote": "a quote that is definitely not present here at all"}
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.ABSENT


def test_medium_mismatch_is_unverifiable_not_checked():
    c = coverage([Verdict.MEDIUM_MISMATCH, Verdict.EXACT])
    assert c["checked"] == 1 and c["unverifiable"] == 1 and c["failures"] == 0
