"""A 200 response is not proof we received the document.

On 2026-10-28 this checker reported `FAIL Quote NOT found at source URL` for a
sound Goodreads entry. The fetch had succeeded — and returned a 13,234-character
JS shell that contains no review text at all. The quote was not absent; the
document was never delivered.

That is the worse half of the same bug that let unreachable pages pass. A false
WARN lets a bad quote through; a false FAIL blocks a good entry and teaches
everyone that the gate is noise. Both come from treating "the request
succeeded" as "I have the text".

So a miss only counts as refutation when there is positive evidence we are
looking at the right page.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_quotes import is_conclusive  # noqa: E402

ATTRIB = "Jeff Berman"
QUOTE = "we have fetishized shareholder returns at the cost of other stakeholders"


def test_a_tiny_shell_page_is_inconclusive():
    """13KB of markup with no article body — the real Goodreads failure."""
    assert is_conclusive(page="<html><head></head><body><div id=app></div></body></html>",
                         quote=QUOTE, attribution=ATTRIB) is False


def test_a_real_page_mentioning_the_author_is_conclusive():
    """The author's name present means we reached their post; a miss is real."""
    page = "x" * 3000 + " A review by Jeff Berman about something else entirely."
    assert is_conclusive(page=page, quote=QUOTE, attribution=ATTRIB) is True


def test_a_real_page_containing_the_quote_opening_is_conclusive():
    """Opening present, remainder absent — the composite case must stay catchable."""
    page = "y" * 3000 + " " + QUOTE[:40] + " and then something nobody said."
    assert is_conclusive(page=page, quote=QUOTE, attribution="Someone Else") is True


def test_a_long_page_with_neither_signal_is_inconclusive():
    """A cookie wall or captcha can be long and still not be the document."""
    page = "Please enable JavaScript to continue. " * 200
    assert is_conclusive(page=page, quote=QUOTE, attribution=ATTRIB) is False


def test_empty_page_is_inconclusive():
    assert is_conclusive(page="", quote=QUOTE, attribution=ATTRIB) is False


def test_missing_attribution_does_not_crash():
    page = "z" * 3000 + " " + QUOTE[:40]
    assert is_conclusive(page=page, quote=QUOTE, attribution=None) is True


def test_attribution_match_is_case_insensitive():
    page = "w" * 3000 + " reviewed by JEFF BERMAN here"
    assert is_conclusive(page=page, quote=QUOTE, attribution=ATTRIB) is True


def test_very_short_quote_cannot_carry_the_prefix_signal():
    """A 10-char quote prefix would match almost anything; require the name."""
    page = "q" * 3000 + " astounding "
    assert is_conclusive(page=page, quote="astounding",
                         attribution="Nobody Here") is False


# --- the signals must be read from visible text, not from markup ---------------------

YOUTUBE_SHELL = (
    '<html><head><meta name="author" content="Stanford eCorner">'
    '<script>var ytInitialData={"channel":"Stanford eCorner","x":"' + "z" * 40000 + '"};</script>'
    '</head><body><div id="app"></div></body></html>'
)


def test_a_huge_shell_with_the_name_only_in_markup_is_inconclusive():
    """The 2026-10-30 false FAIL, exactly.

    A YouTube watch page is hundreds of KB of raw HTML, so the length floor
    passes, and the channel name sits in metadata, so the attribution signal
    fires — while the transcript the quote came from is nowhere in the HTML at
    all. Both signals have to be read from VISIBLE text or markup answers for
    the document.
    """
    assert is_conclusive(page=YOUTUBE_SHELL, quote=QUOTE,
                         attribution="Stanford eCorner") is False


def test_a_real_page_with_the_name_in_body_text_is_still_conclusive():
    page = "<html><body><p>" + ("lorem ipsum " * 300) + " reviewed by Jeff Berman</p></body></html>"
    assert is_conclusive(page=page, quote=QUOTE, attribution=ATTRIB) is True


def test_script_bodies_do_not_pad_the_length_floor():
    """A page that is all script and no prose cannot clear the floor."""
    page = "<html><body><script>" + ("x" * 50000) + "</script><p>hi</p></body></html>"
    assert is_conclusive(page=page, quote=QUOTE, attribution=ATTRIB) is False
