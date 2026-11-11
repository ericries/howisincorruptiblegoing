"""Tests for the social comment archive's Twitter/X ingestion.

Eric, 2026-10-20: "you can add the twitter and cardono comments to the comment
archive. expand it to include cases like that."

The archive was LinkedIn-only and kept short superlatives. Two things change:

  - **Platform.** X replies to @ericries are the same material. Kevin Payne's
    "Metrics outlive principles. Once the dashboard rewards extraction, the
    people who remember why the company worked stop getting promoted" is a
    better line than most of what the LinkedIn lane produces, and the Cardano
    Foundation governance crowd reading it is exactly the kind of adoption
    signal worth keeping.
  - **"Cases like that."** Not only praise. A sharp observation that uses the
    book's argument counts, which is why the queue is classified by judgment in
    the cron turn rather than by a praise regex.

Low engagement is not disqualifying here. The archive is raw material for social
posts, not the timeline — a zero-like reply with a great sentence is useful, and
a 500-like "congrats!" is not.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "archive_social_comments",
    Path(__file__).resolve().parent / "archive-social-comments.py",
)
asc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(asc)


def tweet(**kw):
    base = {
        "id": "2112680802366697543",
        "url": "https://x.com/kevintpayne/status/2112680802366697543",
        "text": "@ericries Governance is cheapest when there is little to unwind.",
        "createdAt": "Tue Oct 20 23:02:09 +0000 2026",
        "likeCount": 0, "replyCount": 0, "viewCount": 1,
        "isReply": True, "isRetweet": False, "isQuote": False,
        "inReplyToUsername": "ericries",
        "conversationId": "2112661429618700662",
        "author": {"userName": "kevintpayne", "name": "Kevin Payne",
                   "description": "GTM Engineer at LawVu", "followers": 23763,
                   "url": "https://x.com/kevintpayne"},
    }
    base.update(kw)
    return base


# --- what gets queued ---------------------------------------------------------------

def test_a_reply_to_eric_is_queued():
    q = asc.queue_from_tweets([tweet()], scan_source="twitter-mentions", seen=set())
    assert len(q) == 1
    r = q[0]
    assert r["platform"] == "twitter"
    assert r["kind"] == "comment"
    assert r["identifier"] == "tweet:2112680802366697543"
    assert r["permalink"] == "https://x.com/kevintpayne/status/2112680802366697543"
    assert r["author"]["name"] == "Kevin Payne"
    assert r["author"]["profile_url"] == "https://x.com/kevintpayne"
    assert r["reactions"] == 0


def test_a_reply_to_eric_inherits_the_book_anchor():
    # Mirrors the LinkedIn author-feed rule: a reply under Eric's own post is
    # about the book even when it never names it. This is the whole Kevin Payne
    # case — his best lines never say "Incorruptible".
    t = tweet(text="Metrics outlive principles. Once the dashboard rewards "
                   "extraction, the people who remember why the company worked "
                   "stop getting promoted.")
    assert len(asc.queue_from_tweets([t], scan_source="twitter-mentions", seen=set())) == 1


def test_a_standalone_tweet_naming_the_book_is_queued():
    t = tweet(isReply=False, inReplyToUsername=None,
              text="one chapter into Incorruptible and i love it")
    assert len(asc.queue_from_tweets([t], scan_source="twitter-mentions", seen=set())) == 1


def test_an_unrelated_tweet_is_not_queued():
    t = tweet(isReply=False, inReplyToUsername=None,
              text="after 60 squats am strength session, here goes monday")
    assert asc.queue_from_tweets([t], scan_source="twitter-mentions", seen=set()) == []


# --- what is filtered out before a human ever reads it ------------------------------

def test_erics_own_tweets_are_skipped():
    t = tweet(author={"userName": "ericries", "name": "Eric Ries", "url": "https://x.com/ericries"})
    assert asc.queue_from_tweets([t], scan_source="twitter-mentions", seen=set()) == []


def test_retweets_are_skipped():
    assert asc.queue_from_tweets([tweet(isRetweet=True)],
                                 scan_source="twitter-mentions", seen=set()) == []


def test_already_seen_identifiers_are_skipped():
    seen = {"tweet:2112680802366697543"}
    assert asc.queue_from_tweets([tweet()], scan_source="twitter-mentions", seen=seen) == []


def test_an_empty_tweet_is_skipped():
    assert asc.queue_from_tweets([tweet(text="   ")],
                                 scan_source="twitter-mentions", seen=set()) == []


# --- the reply's context travels with it --------------------------------------------

def test_the_parent_tweet_is_attached_when_present_in_the_batch():
    parent = tweet(id="2112661429618700662",
                   url="https://x.com/ericries/status/2112661429618700662",
                   text="Governance debt compounds quietly.",
                   isReply=False, inReplyToUsername=None,
                   author={"userName": "ericries", "name": "Eric Ries",
                           "url": "https://x.com/ericries"})
    q = asc.queue_from_tweets([parent, tweet()], scan_source="twitter-mentions", seen=set())
    assert len(q) == 1, "Eric's own tweet is skipped as a candidate but kept as context"
    assert q[0]["parent_post"]["text"] == "Governance debt compounds quietly."
    assert q[0]["parent_post"]["author"]["name"] == "Eric Ries"


def test_a_missing_parent_degrades_to_none_rather_than_crashing():
    q = asc.queue_from_tweets([tweet()], scan_source="twitter-mentions", seen=set())
    assert q[0]["parent_post"] is None


# --- dates --------------------------------------------------------------------------

def test_twitter_date_is_normalised_to_iso():
    q = asc.queue_from_tweets([tweet()], scan_source="twitter-mentions", seen=set())
    assert q[0]["posted_at"].startswith("2026-10-20T23:02:09")


def test_an_unparseable_date_does_not_drop_the_record():
    q = asc.queue_from_tweets([tweet(createdAt="not a date")],
                              scan_source="twitter-mentions", seen=set())
    assert len(q) == 1
    assert q[0]["posted_at"] in (None, "not a date")


# --- platform tagging ---------------------------------------------------------------

def test_linkedin_records_are_tagged_with_their_platform_too():
    # The archive directory is still named linkedin-comments for continuity with
    # the site's reader-quote pipeline, so the platform field is what actually
    # distinguishes the sources now.
    post = {
        "content": "Incorruptible is superb.",
        "author": {"name": "Someone", "info": "CEO",
                   "linkedinUrl": "https://www.linkedin.com/in/someone"},
        "postedAt": {"date": "2026-10-20T10:00:00.000Z"},
        "engagement": {"likes": 3, "comments": 0},
        "id": "urn:li:activity:7518000000000000000",
    }
    q = asc.queue_from_posts([post], scan_source="linkedin-keyword", seen=set())
    assert len(q) == 1
    assert q[0]["platform"] == "linkedin"


# --- the platform must survive the write ---------------------------------------------

def test_applied_verdicts_keep_their_platform(tmp_path, monkeypatch):
    # The record written to the archive is built from a fixed field list, so a
    # new field is silently dropped unless it is added there. On the first run
    # all 8 twitter records landed tagged as linkedin.
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())

    vp = tmp_path / "verdicts.json"
    vp.write_text(json.dumps([{
        "identifier": "tweet:1", "platform": "twitter", "kind": "comment",
        "source_scan": "twitter-mentions",
        "text": "Metrics outlive principles, and the dashboard decides who gets promoted.",
        "pull_quote": "Metrics outlive principles",
        "permalink": "https://x.com/kevintpayne/status/1",
        "author": {"name": "Kevin Payne", "profile_url": "https://x.com/kevintpayne"},
    }]))
    assert asc._apply_verdicts_mode(vp) == 0

    written = json.loads(next(tmp_path.glob("2*.json")).read_text())
    assert written[-1]["platform"] == "twitter"


def test_a_verdict_without_a_platform_defaults_to_linkedin(tmp_path, monkeypatch):
    # 40 days of existing archive files predate the field.
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{
        "identifier": "comment:9", "kind": "comment", "source_scan": "linkedin-keyword",
        "text": "This book is astounding and I cannot stop recommending it.",
        "pull_quote": "astounding",
        "author": {"name": "Someone"},
    }]))
    assert asc._apply_verdicts_mode(vp) == 0
    written = json.loads(next(tmp_path.glob("2*.json")).read_text())
    assert written[-1]["platform"] == "linkedin"


# --- the watermark writes itself ----------------------------------------------------

def test_applying_verdicts_writes_the_watermark(tmp_path, monkeypatch):
    # The prompt used to end with "then write the watermark" as a separate step.
    # It was missing entirely until 2026-10-20, so scan_catchup reported the job
    # as never having run. An instruction that is a one-liner at the end of a
    # long prompt is the easiest kind to skip; the script knows it has finished,
    # so the script records it.
    import scan_state
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    written = {}
    monkeypatch.setattr(asc, "write_watermark", lambda src, when: written.update({src: when}))

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{
        "identifier": "comment:1", "kind": "comment", "source_scan": "linkedin-keyword",
        "text": "This book is astounding and I keep recommending it to founders.",
        "pull_quote": "astounding", "author": {"name": "Someone"},
    }]))
    asc._apply_verdicts_mode(vp)
    assert written.get("linkedin-comments"), "watermark not written"


def test_the_watermark_is_not_written_when_nothing_was_applied(tmp_path, monkeypatch):
    # A run that archived nothing has not covered the window either.
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: {"comment:1"})
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    written = {}
    monkeypatch.setattr(asc, "write_watermark", lambda src, when: written.update({src: when}))
    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{"identifier": "comment:1", "kind": "comment",
                               "text": "already seen, long enough to pass the floor",
                               "pull_quote": "x", "author": {}}]))
    asc._apply_verdicts_mode(vp)
    assert written == {}


# --- two-word superlatives ---------------------------------------------------------

def test_a_two_word_superlative_is_archived(tmp_path, monkeypatch):
    """Eric, 2026-10-23: "please include all two-word superlatives for use in
    future social media posters. 'excellent book!!' definitely counts."

    The apply-verdicts path carried a 12-character floor, so "Great book!" (11)
    was judged a keeper and then silently dropped by the length gate on
    2026-10-23. A verdict has already been through judgment; the floor's only
    remaining job is to reject an empty or emoji-only record.
    """
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    monkeypatch.setattr(asc, "write_watermark", lambda *a, **k: None)

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([
        {"identifier": "c:1", "kind": "comment", "text": "Great book!",
         "pull_quote": "Great book!", "author": {"name": "A"}},
        {"identifier": "c:2", "kind": "comment", "text": "excellent book!!",
         "pull_quote": "excellent book!!", "author": {"name": "B"}},
        {"identifier": "c:3", "kind": "comment", "text": "astounding",
         "pull_quote": "astounding", "author": {"name": "C"}},
    ]))
    asc._apply_verdicts_mode(vp)
    written = json.loads(next(tmp_path.glob("2*.json")).read_text())
    assert {r["pull_quote"] for r in written} == {"Great book!", "excellent book!!", "astounding"}


def test_an_emoji_only_comment_is_still_dropped(tmp_path, monkeypatch):
    # The floor still has a job: 👏 on its own is not a superlative.
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    monkeypatch.setattr(asc, "write_watermark", lambda *a, **k: None)
    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{"identifier": "c:9", "kind": "comment",
                               "text": " 👏 ", "pull_quote": "👏", "author": {}}]))
    asc._apply_verdicts_mode(vp)
    files = list(tmp_path.glob("2*.json"))
    written = json.loads(files[0].read_text()) if files else []
    assert written == []


# --- a skip is a judgment, and judgments must be recorded ----------------------

def test_a_skip_verdict_is_recorded_so_it_stops_returning_to_the_queue(tmp_path, monkeypatch):
    """A rejected candidate was recorded nowhere, so it came back every run.

    The cron prompt carried the consequence as a standing instruction — "a
    SKIPPED comment is recorded nowhere, so the same rejects return to the
    queue every run — judge them consistently rather than drifting". That is
    prose compensating for a missing mechanism: consistency was being asked of
    my memory across nights instead of being made structural.

    Recording the skip fixes that, and fixes a second thing with the same
    cause. `_apply_verdicts_mode` could not tell "I judged eleven and kept
    none" from "I was called with nothing", so the watermark was gated on
    `added` and an all-skip cycle left no record the job had run. A recorded
    skip is evidence of judgment, so the watermark can follow it.
    """
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "SKIPPED_PATH", tmp_path / ".skipped.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    written = {}
    monkeypatch.setattr(asc, "write_watermark", lambda src, when: written.update({src: when}))

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([
        {"identifier": "tweet:1", "decision": "skip", "reason": "question, not an observation"},
        {"identifier": "tweet:2", "decision": "skip", "reason": "quotes the book back"},
    ]))
    assert asc._apply_verdicts_mode(vp) == 0

    skipped = json.loads((tmp_path / ".skipped.json").read_text())
    assert {r["identifier"] for r in skipped} == {"tweet:1", "tweet:2"}
    assert any("question" in r.get("reason", "") for r in skipped), "the reason is the point"

    # Nothing was archived, but judgment happened, so the cycle is recorded.
    assert written.get("linkedin-comments"), "a judged cycle must record that it ran"

    # And the archive itself stays empty — a skip is not a keeper.
    today = __import__("datetime").date.today().isoformat()
    archive = tmp_path / f"{today}.json"
    assert not archive.exists() or json.loads(archive.read_text()) == []


def test_a_recorded_skip_is_excluded_from_a_later_queue(tmp_path, monkeypatch):
    """The same reject must not come back for re-judgment next run."""
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "SKIPPED_PATH", tmp_path / ".skipped.json")
    (tmp_path / ".skipped.json").write_text(json.dumps(
        [{"identifier": "tweet:1", "reason": "question", "skipped_at": "2026-10-31"}]))

    asc._persist_queue([
        {"identifier": "tweet:1", "full_text": "already judged and rejected"},
        {"identifier": "tweet:9", "full_text": "genuinely new candidate"},
    ])
    queued = json.loads((tmp_path / ".llm-queue.json").read_text())
    assert [q["identifier"] for q in queued] == ["tweet:9"]


def test_an_empty_verdicts_file_still_writes_no_watermark(tmp_path, monkeypatch):
    """No judgment happened, so nothing is claimed about the window.

    This is the distinction the old `if added` gate was reaching for and could
    not express.
    """
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "SKIPPED_PATH", tmp_path / ".skipped.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())
    written = {}
    monkeypatch.setattr(asc, "write_watermark", lambda src, when: written.update({src: when}))

    vp = tmp_path / "v.json"
    vp.write_text("[]")
    asc._apply_verdicts_mode(vp)
    assert written == {}


# --- quotes_the_book carries the verdict's judgment ---------------------------------

def test_a_verdict_can_mark_that_the_pull_quote_is_the_books_own_words(tmp_path, monkeypatch):
    # FORMAT-NOTES item 6 asks for this field because it changes how the social
    # agent attributes the card. It was written as a literal False on every
    # record, so 200 of 208 said "their own opinion" without anything having
    # looked. Rajen Sanghvi (2026-11-03) opened a post on a sentence he credited
    # to the book — the exact case the field was requested for.
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{
        "identifier": "activity:1", "kind": "post", "source_scan": "linkedin-keyword",
        "text": "“Trust creates alignment. Alignment enables speed.” We talk about trust a lot here.",
        "pull_quote": "Trust creates alignment. Alignment enables speed.",
        "quotes_the_book": True,
        "author": {"name": "Rajen Sanghvi"},
    }]))
    assert asc._apply_verdicts_mode(vp) == 0
    assert json.loads(next(tmp_path.glob("2*.json")).read_text())[-1]["quotes_the_book"] is True


def test_quotes_the_book_defaults_to_false_when_the_verdict_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_load_seen_identifiers", lambda: set())
    monkeypatch.setattr(asc, "_load_known_source_urls", lambda: set())
    monkeypatch.setattr(asc, "_load_known_author_names", lambda: set())

    vp = tmp_path / "v.json"
    vp.write_text(json.dumps([{
        "identifier": "activity:2", "kind": "post", "source_scan": "linkedin-keyword",
        "text": "Best business book I have read in years, no question about it.",
        "pull_quote": "Best business book I have read in years",
        "author": {"name": "Someone Else"},
    }]))
    assert asc._apply_verdicts_mode(vp) == 0
    assert json.loads(next(tmp_path.glob("2*.json")).read_text())[-1]["quotes_the_book"] is False


def test_apply_verdicts_refuses_a_pull_quote_that_is_not_verbatim(tmp_path, monkeypatch):
    """The prompt has said since October that "a one-line `assert pq in text` in
    the verdict-writing script makes this impossible to get wrong" — but that
    script is a scratch file written fresh each cycle, so it is a habit, not a
    mechanism. On 2026-11-09 the habit held in the scratch script and the apply
    ran anyway, writing a quote with a curly apostrophe the source spells
    straight. An audit then found 16 older records the same way: spans lifted and
    tidied with a capital letter or a full stop the writer never used. The tool
    refuses them now.
    """

    v = [{"identifier": "comment:1", "decision": "keep",
          "text": "He said it starts in a company's genesis.",
          "pull_quote": "it starts in a company’s genesis.",   # curly, source is straight
          "author": {"name": "T"}, "permalink": "x", "kind": "comment"}]
    p = tmp_path / "v.json"
    p.write_text(json.dumps(v))
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    rc = asc._apply_verdicts_mode(p)
    assert rc != 0, "a non-verbatim pull_quote must fail the apply"


def test_apply_verdicts_accepts_a_verbatim_pull_quote(tmp_path, monkeypatch):

    v = [{"identifier": "comment:2", "decision": "keep",
          "text": "He said it starts in a company's genesis.",
          "pull_quote": "it starts in a company's genesis.",
          "author": {"name": "T"}, "permalink": "x", "kind": "comment"}]
    p = tmp_path / "v.json"
    p.write_text(json.dumps(v))
    monkeypatch.setattr(asc, "ARCHIVE_DIR", tmp_path)
    assert asc._apply_verdicts_mode(p) == 0


def test_queue_message_counts_what_was_actually_added(tmp_path, monkeypatch, capsys):
    """"N new candidates added" must mean N, not N-before-dedup.

    On 2026-11-10 the X lane printed "15 new candidates added (1 total
    pending)" — two numbers that cannot both be true of the same run. Fourteen
    had been judged on earlier cycles and were correctly dropped, but the
    message reported the pre-dedup count under the word "added", so the run
    read as though fourteen candidates had vanished between one clause and the
    next. A cycle was spent proving nothing was lost. The count has to be of
    what crossed the boundary, which is the same lesson as `count_by_shape`:
    a number takes its meaning from what was measured, not from the variable
    it was nearest.
    """
    monkeypatch.setattr(asc, "LLM_QUEUE_PATH", tmp_path / ".llm-queue.json")
    monkeypatch.setattr(asc, "_skipped_identifiers", lambda: {"a", "b"})
    asc._persist_queue([{"identifier": "a"}, {"identifier": "b"}, {"identifier": "c"}])
    out = capsys.readouterr().out
    assert "1 new candidate" in out, out
    assert "15 new candidates" not in out
    assert "(1 total pending)" in out, out
