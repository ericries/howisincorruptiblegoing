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
