"""Tests for the scan triage helper (scripts/scan-triage.py).

Run: uv run --with pytest pytest scripts/test_scan_triage.py
"""
import importlib.util, json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "scan_triage", Path(__file__).resolve().parent / "scan-triage.py"
)
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


# --- normalise_items: each platform's item shape reduces to one common record ---

def test_linkedin_item_normalises():
    item = {
        "linkedinUrl": "https://www.linkedin.com/posts/foo_bar-activity-123-xy",
        "content": "Eric Ries's Incorruptible is excellent.",
        "author": {"name": "Jane Doe", "info": "CEO, Example"},
        "engagement": {"likes": 12, "comments": 3},
        "postedAt": {"date": "2026-10-04T10:00:00.000Z"},
    }
    r = st.normalise(item, "linkedin")
    assert r["author"] == "Jane Doe"
    assert r["headline"] == "CEO, Example"
    assert r["likes"] == 12
    assert r["url"].endswith("-activity-123-xy")
    assert r["date"] == "2026-10-04"
    assert "Incorruptible" in r["text"]


def test_twitter_item_normalises():
    item = {
        "fullText": "Incorruptible is great",
        "url": "https://x.com/a/status/1",
        "createdAt": "Sat Oct 04 13:31:00 +0000 2026",
        "likeCount": 4, "viewCount": 99, "isReply": True,
        "author": {"userName": "someone", "followers": 500},
    }
    r = st.normalise(item, "twitter")
    assert r["author"] == "@someone"
    assert r["likes"] == 4
    assert r["is_reply"] is True
    assert r["followers"] == 500


def test_tiktok_item_normalises():
    item = {
        "id": "7692170403183168782", "text": "What is strategy, really?",
        "createTimeISO": "2026-10-02T12:00:00.000Z",
        "isSlideshow": False, "playCount": 152,
        "videoMeta": {"duration": 39},
        "webVideoUrl": "https://www.tiktok.com/@ericriesactual/video/7692170403183168782",
    }
    r = st.normalise(item, "tiktok")
    assert r["id"] == "7692170403183168782"
    assert r["duration"] == 39
    assert r["slideshow"] is False
    assert r["plays"] == 152


def test_youtube_item_normalises():
    item = {
        "title": "Eric Ries on X", "url": "https://youtube.com/watch?v=abc",
        "date": "2026-10-04T00:00:00.000Z", "channelName": "Chan",
        "numberOfSubscribers": 2440, "viewCount": 310, "duration": "00:44:52",
    }
    r = st.normalise(item, "youtube")
    assert r["author"] == "Chan"
    assert r["subscribers"] == 2440
    assert r["views"] == 310


# --- dedupe against what is already shipped ---

def test_already_shipped_matches_on_normalised_url():
    shipped = {st.norm_url("https://www.linkedin.com/posts/foo_bar-activity-123-xy")}
    assert st.is_shipped("https://linkedin.com/posts/foo_bar-activity-123-xy?utm=1", shipped)
    assert not st.is_shipped("https://www.linkedin.com/posts/other-activity-999-zz", shipped)


def test_youtube_watch_urls_do_not_collide():
    """?v= carries the identity of a YouTube URL — stripping the whole query
    string made every watch URL normalise to 'youtube.com/watch' and report
    SHIPPED (observed 2026-10-04 against the real scan data)."""
    shipped = {st.norm_url("https://www.youtube.com/watch?v=aobQIEU5dhE")}
    assert st.is_shipped("https://youtube.com/watch?v=aobQIEU5dhE", shipped)
    assert not st.is_shipped("https://www.youtube.com/watch?v=duhLiS1Ic3s", shipped)


def test_tracking_params_are_still_ignored():
    shipped = {st.norm_url("https://www.youtube.com/watch?v=abc")}
    assert st.is_shipped("https://www.youtube.com/watch?v=abc&utm_source=li&si=xyz&t=30", shipped)


def test_query_param_order_does_not_matter():
    shipped = {st.norm_url("https://ex.com/p?b=2&a=1")}
    assert st.is_shipped("https://ex.com/p?a=1&b=2", shipped)


def test_known_authors_flags_repeat_poster():
    known = {"brian behm": ["2026-10-01-brian-behm-wild-construct-board-metrics"]}
    assert st.author_already_shipped("Brian Behm", known) == [
        "2026-10-01-brian-behm-wild-construct-board-metrics"
    ]
    assert st.author_already_shipped("Someone Else", known) == []


# --- the full-text escape hatch: never truncate when asked for one item ---

def test_render_full_does_not_truncate():
    long_text = "x" * 5000 + " Eric Ries's book Incorruptible is a big inspiration"
    rec = {"author": "A", "headline": "", "url": "u", "date": "d",
           "likes": 0, "text": long_text}
    out = st.render_full(rec)
    assert long_text in out, "render_full must emit the entire post body"


def test_render_table_truncates_but_marks_it():
    rec = {"author": "A", "headline": "h", "url": "u", "date": "2026-10-04",
           "likes": 1, "text": "y" * 900}
    line = st.render_row(rec, width=120)
    assert len(line) < 400
    assert "…" in line, "truncated rows must be visibly marked as truncated"


# --- BELOW-FOLD detection ----------------------------------------------------------
# The costliest recurring failure is not recall, it is judgment: a post whose
# book citation sits below the truncation point gets dismissed from the row.
# Fora Fereydouni (47 reactions) was passed over inside a 13-item list on
# 2026-10-06 and shipped five days late; Paige Kaye was nearly lost the same way.
# See docs/postmortems/2026-10-16-five-whys-cadence-and-citation.md thread 2.

def test_below_fold_when_citation_is_past_the_cut():
    text = ("Every time I had taken myself out of the story, I start building the wrong "
            "company. I have noticed it in big decisions, but also in something as small "
            "as a pitch, where I explained the problem and the market and still walked "
            "away knowing something was missing. " * 2
            + "That is one reason Eric Ries's Incorruptible stayed with me.")
    assert st.citation_below_fold(text, width=150) is True


def test_not_below_fold_when_citation_is_visible_in_the_row():
    text = "I finished Incorruptible by Eric Ries last week. " + ("More thoughts. " * 40)
    assert st.citation_below_fold(text, width=150) is False


def test_not_below_fold_when_post_is_shorter_than_the_cut():
    assert st.citation_below_fold("Short post mentioning Eric Ries.", width=150) is False


def test_not_below_fold_when_there_is_no_citation_at_all():
    assert st.citation_below_fold("x" * 400, width=150) is False


def test_below_fold_matches_either_book_or_author():
    tail_author = ("y" * 300) + " credit to Eric Ries for this framing"
    tail_book = ("y" * 300) + " straight out of Incorruptible"
    assert st.citation_below_fold(tail_author, width=150) is True
    assert st.citation_below_fold(tail_book, width=150) is True


def test_below_fold_is_case_insensitive():
    assert st.citation_below_fold(("z" * 300) + " read INCORRUPTIBLE", width=150) is True


def test_below_fold_respects_the_width_actually_used():
    # a wider row shows more, so the same post may no longer be below the fold
    text = ("w" * 200) + " Eric Ries " + ("w" * 200)
    assert st.citation_below_fold(text, width=150) is True
    assert st.citation_below_fold(text, width=400) is False


def test_below_fold_handles_whitespace_collapse_like_render_row():
    # render_row collapses runs of whitespace before truncating; detection must
    # measure against the same collapsed string or the offsets disagree
    text = "a" + ("\n\n   " * 60) + "b Eric Ries"
    assert st.citation_below_fold(text, width=150) is False


# --- row composition: never truncate the citation out of view ----------------------
# Flagging below-fold citations proved accurate but fired on ~1/3 of rows, which is
# too common to stand out. Better to fix the row: when the book mention falls past
# the cut, show the opening AND the sentence that mentions it, so the reader never
# has to know the flag existed.

def test_row_shows_citation_context_when_it_would_be_truncated():
    text = ("Every time I had taken myself out of the story, I start building the wrong "
            "company. " * 4
            + "That is one reason Eric Ries's Incorruptible stayed with me. "
            + "Growth is never a good enough reason to become careless with that trust.")
    row = st.render_row({"text": text}, width=150)
    assert "Incorruptible" in row, "the citation must survive truncation"
    assert row.startswith("Every time I had taken myself"), "opening is still shown"
    assert "…" in row, "the elision is visible"


def test_row_is_unchanged_when_citation_already_visible():
    text = "I finished Incorruptible by Eric Ries last week. " + ("More thoughts. " * 40)
    row = st.render_row({"text": text}, width=150)
    assert row == text[:150] + "…"


def test_row_unchanged_for_short_posts():
    text = "Short post mentioning Eric Ries."
    assert st.render_row({"text": text}, width=150) == text


def test_row_unchanged_when_post_never_mentions_the_book():
    text = "q" * 400
    assert st.render_row({"text": text}, width=150) == "q" * 150 + "…"


def test_row_stays_within_a_sane_length_budget():
    text = ("p" * 500) + " thanks to Eric Ries for this " + ("p" * 500)
    row = st.render_row({"text": text}, width=150)
    assert len(row) <= 150 * 2 + 20, "recomposed row must not blow up the output"
    assert "Eric Ries" in row
