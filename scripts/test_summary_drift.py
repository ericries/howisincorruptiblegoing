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
