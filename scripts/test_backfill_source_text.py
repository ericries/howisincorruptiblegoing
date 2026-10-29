"""Recover the source text for entries that shipped without it.

625 entries carry a blockquote and no captured source text, so nothing can
verify them. The forward gate (`quote_integrity --require-capture`) stops the
backlog growing; this recovers what can still be recovered.

The rule that matters here is that a BAD capture is worse than no capture. A
saved JS shell or cookie wall would make `quote_integrity` report ABSENT for a
sound entry — manufacturing exactly the false accusations that the first run of
that checker produced. So nothing is written unless the text is plausibly the
document, and "contains the quote" is deliberately NOT the test: that would be
circular and would guarantee every capture verifies.
"""

from __future__ import annotations

import json

import pytest

from backfill_source_text import (
    build_record,
    extract_text,
    should_save,
)


# --- turning a page into text ---------------------------------------------------------

def test_extract_strips_tags_and_unescapes():
    html = "<p>It&#39;s <b>governance</b> &amp; purpose</p>"
    assert extract_text(html) == "It's governance & purpose"


def test_extract_drops_script_and_style_bodies():
    """Script bodies are most of a modern page and none of its text."""
    html = "<style>.a{color:red}</style><script>var x='quote';</script><p>Real words</p>"
    assert extract_text(html) == "Real words"


def test_extract_collapses_whitespace_across_tags():
    """A quote spanning two paragraphs must come out as one line.

    The endorsement blurbs on incorruptible.co are split across markup; a raw
    substring test against the HTML found none of them.
    """
    assert extract_text("<p>first half</p>\n\n<p>second half</p>") == "first half second half"


def test_extract_handles_empty_input():
    assert extract_text("") == ""


# --- refusing to save a shell ---------------------------------------------------------

def test_will_not_save_a_js_shell():
    """YouTube returns ~250 characters of extracted text. Saving that would
    make every video entry report ABSENT."""
    entry = {"id": "e", "blockquote": "a" * 80, "attribution": "Someone"}
    assert should_save(entry, "Enable JavaScript to continue") is False


def test_will_not_save_a_cookie_wall_however_long():
    entry = {"id": "e", "blockquote": "a" * 80, "attribution": "Someone"}
    wall = "We use cookies to improve your experience. " * 80
    assert should_save(entry, wall) is False


def test_saves_a_page_that_names_the_author():
    entry = {"id": "e", "blockquote": "x" * 80, "attribution": "Rita McGrath"}
    page = "lorem " * 400 + " an article by Rita McGrath about governance"
    assert should_save(entry, page) is True


def test_saves_a_page_carrying_the_quote():
    entry = {"id": "e", "blockquote": "the ratchet only turns one way", "attribution": "Nobody"}
    page = "lorem " * 400 + " he wrote that the ratchet only turns one way today"
    assert should_save(entry, page) is True


def test_does_not_require_the_quote_to_match():
    """Saving only quote-matching text would make the checker vacuous.

    A capture that proves the entry WRONG is the most valuable kind. The gate
    is "is this the document", never "does this agree with us".
    """
    entry = {"id": "e", "blockquote": "something we claimed", "attribution": "Rita McGrath"}
    page = "lorem " * 400 + " Rita McGrath wrote something entirely different"
    assert should_save(entry, page) is True


# --- the record written to disk -------------------------------------------------------

def test_build_record_has_the_fields_the_checker_reads():
    entry = {"id": "e1", "source_url": "https://example.com/p", "attribution": "A"}
    rec = build_record(entry, "the text", platform="web", captured_at="2026-10-28T00:00:00Z")
    assert rec["entry_id"] == "e1"
    assert rec["source_url"] == "https://example.com/p"
    assert rec["full_text"] == "the text"
    assert rec["platform"] == "web"
    assert rec["chars"] == len("the text")
    assert rec["captured_at"] == "2026-10-28T00:00:00Z"


def test_build_record_marks_how_it_was_recovered():
    """A backfilled capture is weaker evidence than one taken at ship time:
    the page may have changed in the months since. Say so in the record."""
    rec = build_record({"id": "e", "source_url": "u"}, "t", platform="web",
                       captured_at="2026-10-28T00:00:00Z", backfilled=True)
    assert rec["backfilled"] is True


def test_record_round_trips_through_the_checker(tmp_path):
    """The written file must be readable by quote_integrity, not just by us."""
    from quote_integrity import check_entry, Verdict

    entry = {"id": "e", "source_url": "https://example.com/p",
             "blockquote": "the ratchet only turns one way", "attribution": "A"}
    rec = build_record(entry, "he said the ratchet only turns one way", platform="web",
                       captured_at="2026-10-28T00:00:00Z", backfilled=True)
    (tmp_path / "e.json").write_text(json.dumps(rec))
    assert check_entry(entry, archive_dir=tmp_path).verdict is Verdict.EXACT


# --- provenance differs by route ------------------------------------------------------

def test_a_short_post_from_a_url_keyed_dataset_is_saved():
    """The 1200-char floor is an HTML heuristic and must not apply here.

    `should_save` guesses whether a fetched PAGE is the right document, because
    a fetch can land on anything. A dataset keyed by post url is different: we
    asked the scraper for that exact url and it returned that exact url, so
    provenance is established, not inferred. Many real LinkedIn posts are
    300-600 characters — applying the page heuristic would have silently
    dropped most of a 353-entry backfill.
    """
    from backfill_source_text import should_save_known_url

    entry = {"id": "e", "blockquote": "short but real", "attribution": "A"}
    assert should_save_known_url(entry, "Short but real post text.") is True


def test_an_empty_or_trivial_dataset_text_is_still_rejected():
    from backfill_source_text import should_save_known_url

    entry = {"id": "e", "blockquote": "q", "attribution": "A"}
    assert should_save_known_url(entry, "") is False
    assert should_save_known_url(entry, "   ") is False


def test_a_bare_domain_root_is_never_captured():
    """A homepage today is not the page the entry quoted months ago.

    The first backfill run stored kpmg.com, octopus.energy and mishcon.com as
    "source text" because `is_conclusive` saw the company name on its own
    homepage. Those captures can only ever produce false ABSENT verdicts, which
    is the exact harm this module is supposed to avoid.
    """
    from backfill_source_text import route_for

    for u in ("https://kpmg.com/", "https://octopus.energy", "http://www.mishcon.com/"):
        assert route_for({"source_url": u}) == "unstable-url", u


def test_a_url_with_a_path_still_routes_to_fetch():
    from backfill_source_text import route_for

    assert route_for({"source_url": "https://kpmg.com/news/some-article"}) == "fetch"
