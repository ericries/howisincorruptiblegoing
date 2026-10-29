"""Blockquotes that silently cut material out of the middle of the source.

Backfilling LinkedIn source text turned up 36 PARTIAL verdicts with one shape:
the quote is made of real source spans, in source order, with unmarked gaps
between them. The 2026-02-12 site-launch entry runs "...aligned brand partner."
straight into a sentence that appears two sentences later, skipping "Huge thanks
to Wunderdogs for building incorruptible.co in record time."

The words are real and the editorial trim is usually sound. What is wrong is
that the cut is invisible, which is what CLAUDE.md means by "never composite".
The repair is to mark each cut with an ellipsis, preserving both the editorial
selection and the reader's ability to see that something was removed.

A repair is only applied when every segment is verbatim in the source and the
segments appear in source order. Anything else is left for a human — a repairer
that guesses would quietly rewrite quotes into something nobody said.
"""

from __future__ import annotations

import pytest

from repair_elisions import ELLIPSIS, repair_quote, segment_quote


SOURCE = (
    "I built this site with care. Finding a partner for a book about "
    "organizational integrity meant finding an aligned brand partner. "
    "Huge thanks to Wunderdogs for building it in record time. "
    "They know how to translate what a company stands for into something people feel."
)


# --- segmenting ------------------------------------------------------------------------

def test_a_contiguous_quote_is_a_single_segment():
    quote = "finding an aligned brand partner"
    assert segment_quote(quote, SOURCE) == [quote]


def test_an_elided_quote_splits_into_its_real_spans():
    quote = ("Finding a partner for a book about organizational integrity meant "
             "finding an aligned brand partner. They know how to translate what a "
             "company stands for into something people feel.")
    segs = segment_quote(quote, SOURCE)
    assert len(segs) == 2
    assert all(s in SOURCE for s in segs), "every segment must be verbatim"


def test_segments_come_back_in_source_order():
    quote = ("Finding a partner for a book about organizational integrity meant "
             "finding an aligned brand partner. They know how to translate what a "
             "company stands for into something people feel.")
    segs = segment_quote(quote, SOURCE)
    assert SOURCE.index(segs[0]) < SOURCE.index(segs[1])


def test_text_not_in_the_source_cannot_be_segmented():
    """A genuinely invented phrase must not be silently dropped into a gap."""
    assert segment_quote("a sentence nobody ever wrote at all", SOURCE) is None


def test_reordered_spans_are_refused():
    """Quoting B then A changes meaning; that is not an elision, it is a rewrite."""
    quote = ("They know how to translate what a company stands for into something "
             "people feel. Finding a partner for a book about organizational integrity "
             "meant finding an aligned brand partner.")
    assert segment_quote(quote, SOURCE) is None


# --- repairing ---------------------------------------------------------------------------

def test_repair_inserts_an_ellipsis_at_the_cut():
    quote = ("Finding a partner for a book about organizational integrity meant "
             "finding an aligned brand partner. They know how to translate what a "
             "company stands for into something people feel.")
    fixed = repair_quote(quote, SOURCE)
    assert ELLIPSIS in fixed
    assert fixed.count(ELLIPSIS) == 1


def test_repaired_quote_keeps_every_original_word():
    quote = ("Finding a partner for a book about organizational integrity meant "
             "finding an aligned brand partner. They know how to translate what a "
             "company stands for into something people feel.")
    fixed = repair_quote(quote, SOURCE)
    for seg in segment_quote(quote, SOURCE):
        assert seg in fixed


def test_a_contiguous_quote_is_returned_unchanged():
    quote = "finding an aligned brand partner"
    assert repair_quote(quote, SOURCE) == quote


def test_repair_returns_none_when_it_cannot_be_done_safely():
    assert repair_quote("invented text that is not present", SOURCE) is None


def test_repair_is_idempotent():
    """Running it twice must not stack ellipses."""
    quote = ("Finding a partner for a book about organizational integrity meant "
             "finding an aligned brand partner. They know how to translate what a "
             "company stands for into something people feel.")
    once = repair_quote(quote, SOURCE)
    assert repair_quote(once, SOURCE) == once


def test_tiny_fragments_do_not_become_segments():
    """Splitting on every stray word would produce confetti, not a quote."""
    assert segment_quote("I a the", SOURCE) is None
