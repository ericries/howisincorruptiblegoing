"""A rewritten summary must not contain facts its sources don't.

Rewriting ~400 summaries means delegating, and a subagent asked to "make this
clearer" will cheerfully supply the clarity — a job title, a company, a round
number — that nothing in the entry supports. That is the single failure mode
that would make this pass worse than leaving the summaries alone, and it is
exactly the kind nobody catches by reading 400 diffs.

So the boundary gets asserted instead: every proper noun and every number in
the new summary must already appear in the old summary, the blockquote, the
title, or the captured source text. New entities are reported for a human.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import summary_drift as sd  # noqa: E402


SRC = {"old": "Courtois ran Microsoft's global sales and operations.",
       "blockquote": "Missions die from unprotected structures.",
       "title": "Jean-Philippe Courtois on unprotected structures",
       "source_text": "I spent forty years at Microsoft. Read it before your next round."}


def new_things(new):
    return sd.introduced(new, **SRC)


def test_a_faithful_rewrite_introduces_nothing():
    assert new_things("Courtois ran Microsoft's global sales and operations for forty years.") == []


def test_an_invented_company_is_caught():
    assert "Salesforce" in new_things("Courtois ran Microsoft and advised Salesforce.")


def test_an_invented_number_is_caught():
    assert "30,000" in new_things("Courtois ran a team of 30,000 at Microsoft.")


def test_a_number_present_as_a_word_in_the_source_is_allowed():
    """The source says 'forty years'; writing '40 years' is a rendering, not a fact."""
    assert new_things("Courtois spent 40 years at Microsoft.") == []


def test_ordinary_sentence_initial_capitals_are_not_entities():
    assert new_things("The post ran long. Missions die from unprotected structures.") == []


def test_a_name_from_the_title_is_allowed():
    assert new_things("Jean-Philippe Courtois ran Microsoft.") == []


def test_a_name_from_the_captured_source_is_allowed():
    assert new_things("Courtois told readers to act before their next round.") == []


def test_multiword_names_are_reported_whole():
    got = new_things("Courtois ran Microsoft and sat on the Sequoia Capital board.")
    assert "Sequoia Capital" in got


def test_a_possessive_matches_its_bare_form():
    assert new_things("Microsoft's scale was the point.") == []


def test_an_invented_name_at_the_start_of_a_sentence_is_caught():
    """Nearly every summary opens with a name, so skipping sentence-initial
    capitals wholesale left the commonest position unchecked."""
    assert "Salesforce" in new_things("Salesforce is the subject of the piece.")


def test_a_known_name_at_the_start_of_a_sentence_is_allowed():
    assert new_things("Microsoft is the subject of the piece.") == []


def test_common_sentence_openers_are_not_treated_as_names():
    for opener in ["The", "He", "She", "They", "After", "His", "Both", "When", "It"]:
        assert new_things(f"{opener} post ran long.") == [], opener


def test_the_attribution_fields_are_legitimate_sources():
    """A rewriter dropped "Founder (YC S18); former PM at Airbnb and Google",
    "Foundry VC", "The No Asshole Rule" and three more, because the drift rule
    named four sources and attribution_title was not among them. Those fields
    are part of the entry and are printed on the card — the most orienting
    detail on the page was the one thing a rewrite could not use."""
    got = sd.introduced("Kirkham founded a YC S18 company and was a PM at Airbnb.",
                        old="A reader posted about the book.",
                        blockquote="A quote.", title="A title",
                        attribution="Josh Kirkham",
                        attribution_title="Founder (YC S18); former PM at Airbnb and Google")
    assert got == []


def test_attribution_name_is_a_source_too():
    assert sd.introduced("Honeyman wrote the review.", old="A reader posted.",
                         attribution="Ryan Honeyman") == []


def test_possessive_pronouns_are_grammar_not_names():
    """"Hers is one of the reader reactions collected on the site" read as an
    invented entity called 'Hers'."""
    for p in ["Hers", "Theirs", "Ours", "We", "Our"]:
        assert new_things(f"{p} came later.") == [], p


# ── the symmetric check: what the rewrite THREW AWAY ─────────────────────
def test_a_fact_dropped_from_the_summary_and_absent_from_the_quote_is_reported():
    """Steve Blank's rewrite cut "intellectual godfather of the lean-startup
    movement" and the judgment that the book is more important than Lean
    Startup. Neither is in his blockquote, so a reader loses them entirely.
    Trimming tics is the job; trimming facts is over-correction."""
    got = sd.dropped(old="Blank is the intellectual godfather of the Lean Startup movement.",
                     new="Blank pioneered customer development.",
                     blockquote="Every once in a while a book comes along.")
    assert "Lean Startup" in got


def test_a_fact_still_carried_by_the_blockquote_is_not_reported():
    """If the quote says it, the reader still gets it — cutting it from the
    summary is exactly the echo rule working."""
    got = sd.dropped(old="He says the causes are structural rather than incidental.",
                     new="Van Brakel is CEO of RSF.",
                     blockquote="The causes are structural rather than incidental.")
    assert got == []


def test_a_fact_kept_in_the_new_summary_is_not_reported():
    assert sd.dropped(old="Blank teaches at Stanford.",
                      new="Blank is an adjunct professor at Stanford.",
                      blockquote="A quote.") == []


def test_dropped_numbers_are_reported():
    got = sd.dropped(old="The post drew 26 likes.", new="He posted about it.",
                     blockquote="A quote.")
    assert "26" in got


def test_a_full_name_shortened_to_a_surname_is_not_a_dropped_fact():
    """House style is surname-only after first reference. Reporting
    "Chris Coleridge" as lost because the rewrite says "Coleridge" buried the
    real losses under noise — 39 of 40 rewrites "dropped" something."""
    assert sd.dropped(old="Chris Coleridge teaches at Cambridge.",
                      new="Coleridge teaches at Cambridge.",
                      blockquote="A quote.") == []


def test_the_book_title_is_never_a_dropped_fact():
    """Every entry is about it; "Incorruptible" -> "the book" is style."""
    assert sd.dropped(old="She recommended Incorruptible on air.",
                      new="She recommended the book on air.",
                      blockquote="A quote.") == []


def test_the_entrys_own_date_is_a_source_for_a_year():
    """A summary saying "published on 28 May 2026" had its "2026" reported as
    unsourced, on an entry dated 2026-03-15. The entry's own date is evidence
    for the year in its own summary."""
    assert sd.introduced("Matt James announced the UK edition in 2026.",
                         old="Matt James announced the UK edition.",
                         entry_date="2026-03-15") == []


def test_a_year_no_source_carries_is_still_reported():
    got = sd.introduced("Matt James announced the UK edition in 2019.",
                        old="Matt James announced the UK edition.",
                        entry_date="2026-03-15")
    assert "2019" in got


def test_capture_includes_corroborating_sources(tmp_path, monkeypatch):
    """A second source on the entry is evidence too.

    An entry that gains a corroborating source_url — an organiser's own
    programme page confirming a workshop first seen in a participant's post —
    can honestly say more than its one capture carries. Before this, every
    such upgrade read as invented detail and the only ways past were to cut
    the fact or to merge two sources into one `full_text`, which is the
    mis-sourced-capture failure this repo has already paid for once.
    """
    monkeypatch.setattr(sd, "CAPTURES", tmp_path)
    (tmp_path / "e1.json").write_text(json.dumps({
        "entry_id": "e1",
        "source_url": "https://example.com/post",
        "full_text": "Mark opened the workshop.",
        "corroborating_sources": [
            {"url": "https://druckerforum.org/2026/pre-events/",
             "text": "The Maria Theresian Apartment, The Hofburg, Vienna."},
        ],
    }))
    hay = sd.capture_for("e1")
    assert "Hofburg" in hay
    assert "Mark opened the workshop." in hay
