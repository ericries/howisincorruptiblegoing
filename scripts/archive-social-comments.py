#!/usr/bin/env python3
"""
scripts/archive-social-comments.py

Builds the local archive of short, quotable social comments about Incorruptible —
raw material for social posts, never shipped to the timeline.

Two input shapes:
  --platform linkedin  Apify harvestapi/linkedin-post-search (posts, plus
                       `comments` arrays when scrapeComments=true)
  --platform twitter   Apify apidojo/tweet-scraper (@ericries mentions/replies)

Anchor-passing items go to a queue; Claude classifies them in the cron turn and
re-runs with --apply-verdicts. Verified records append to
data/archive/linkedin-comments/YYYY-MM-DD.json.

The directory keeps its linkedin-comments name for continuity with the site's
reader-quote pipeline (src/lib/reader-quotes.ts, scripts/promote-reader-quotes.py);
the per-record `platform` field is what distinguishes sources now.

Local-only archive (gitignored) — never pushed to the site. Downstream: the
social-media agent turns these into quote cards + schedules them via Buffer.

Schema per record is documented in
  data/archive/linkedin-comments/FORMAT-NOTES.md
and reference_linkedin_comment_archive.md in memory.

Usage:
  python3 scripts/archive-social-comments.py <scan.json> [--platform linkedin|twitter] [--scan-source=name]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "data" / "archive" / "linkedin-comments"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
ENTRIES_DIR = ROOT / "content" / "entries"
CROSS_POSTS = ROOT / "data" / "cross-posts.json"

# ---- Book-anchor gate ----
# The script emits every anchor-passing item (post/comment mentioning
# Incorruptible / Eric Ries / @ericries, OR under a book-anchored parent,
# OR from Eric's author feed) to:
#   data/archive/linkedin-comments/.llm-queue.json
# The daily cron prompt tells Claude to read that queue, classify each item
# in-turn using its own judgment, and re-run this script with
# `--apply-verdicts <path>` to append verified records to today's archive.
#
# No external LLM API is called and no regex classifier runs. The single
# source of truth for "is this superlative praise?" is Claude's own
# inference in the cron turn (regex retired 2026-09-25 as redundant with
# in-turn classification).

BOOK_ANCHOR_RE = re.compile(
    r"\b(incorruptible|eric\s*ries|@ericries|@ericriesactual)\b",
    re.IGNORECASE,
)

LLM_QUEUE_PATH = ARCHIVE_DIR / ".llm-queue.json"

# Emoji ranges we care about (BMP + supplemental plane pictographs). Also
# catches ⭐/🌟 (U+2B50/U+1F31F) and other common social punctuation.
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F600-\U0001F64F"
    "\U0001F900-\U0001F9FF"
    "]",
    re.UNICODE,
)

URL_RE = re.compile(r"https?://\S+")
COMMENT_URN_RE = re.compile(r"commentUrn=urn%3Ali%3Acomment%3A%28[^)]+%2C(\d+)%29", re.IGNORECASE)
ACTIVITY_ID_RE = re.compile(r"activity[-:](\d+)", re.IGNORECASE)


def _rel(path: Path) -> str:
    """Repo-relative path for display, falling back to the absolute one.

    `Path.relative_to` raises when the target is outside ROOT. That turned a
    cosmetic log line into a hard failure *after* the archive had already been
    written, which is the worst possible place for it.
    """
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def _substantive_text(text: str) -> str:
    """Strip URLs and emoji so the quality gate measures real words, not padding."""
    if not text:
        return ""
    stripped = URL_RE.sub("", text)
    stripped = EMOJI_RE.sub("", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _stable_identifier(*, kind: str, permalink: str | None, raw_id: str | None) -> str | None:
    """Prefer the URL-embedded LinkedIn activity/comment id — the raw `id` field
    varies across harvestapi scan modes for the same underlying object.

    For a comment we prefer the comment id embedded in `commentUrn=`. For a
    post we prefer the numeric part of `activity-<id>-` in the URL slug.
    Falls back to `raw_id` when the URL doesn't include a stable token.
    """
    if permalink:
        if kind == "comment":
            m = COMMENT_URN_RE.search(permalink)
            if m:
                return f"comment:{m.group(1)}"
        # for both posts and comments, activity id is the container id
        m = ACTIVITY_ID_RE.search(permalink)
        if m:
            return f"{'comment' if kind == 'comment' else 'activity'}:{m.group(1)}" if kind == "comment" else f"activity:{m.group(1)}"
    if raw_id:
        return f"{kind}:{raw_id}"
    return None





def has_emoji(text: str) -> bool:
    return bool(EMOJI_RE.search(text or ""))


def _sentence_span_containing(text: str, needle: str) -> str:
    """Return the sentence-like span of `text` that contains `needle`.

    We split on . ? ! or newlines and pick the smallest contiguous chunk that
    contains the needle. If we cannot find it (e.g. needle is emojis or
    matched span crosses sentence boundaries), fall back to the full text.
    """
    if not text or not needle:
        return text or ""
    # Preserve indexes: split by regex on sentence terminators + newlines.
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    lower_needle = needle.lower()
    best = None
    for p in parts:
        if lower_needle in p.lower():
            if best is None or len(p) < len(best):
                best = p
    return best or text.strip()


# ---- normalization ----

def _get(d: dict | None, *keys):
    if not d:
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _author_from(actor_or_author: dict | None) -> dict:
    a = actor_or_author or {}
    return {
        "name": a.get("name"),
        "headline": a.get("position") or a.get("info"),
        "profile_url": a.get("linkedinUrl"),
    }


def _post_permalink(post: dict) -> str | None:
    return _get(post, "linkedinUrl", "shareLinkedinUrl", "url")


def _comment_permalink(cmt: dict) -> str | None:
    return _get(cmt, "linkedinUrl", "url")


# ---- dedupe against already-shipped entries ----

def _load_known_source_urls() -> set[str]:
    urls: set[str] = set()
    if ENTRIES_DIR.exists():
        for f in ENTRIES_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            u = d.get("source_url")
            if u:
                urls.add(u.rstrip("/"))
            for extra in d.get("source_urls") or []:
                if isinstance(extra, dict) and extra.get("url"):
                    urls.add(extra["url"].rstrip("/"))
    if CROSS_POSTS.exists():
        try:
            cp = json.loads(CROSS_POSTS.read_text())
            for item in cp if isinstance(cp, list) else cp.values():
                u = item.get("source_url") if isinstance(item, dict) else None
                if u:
                    urls.add(u.rstrip("/"))
        except Exception:
            pass
    return urls


def _load_known_author_names() -> set[str]:
    names: set[str] = set()
    if ENTRIES_DIR.exists():
        for f in ENTRIES_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            n = (d.get("attribution") or "").strip()
            if n:
                names.add(n.lower())
    return names


def _already_have(permalink: str | None, author_name: str | None,
                  known_urls: set[str], known_names: set[str]) -> bool:
    if permalink and permalink.rstrip("/") in known_urls:
        return True
    if author_name and author_name.strip().lower() in known_names:
        return True
    return False






# ---- Twitter/X ---------------------------------------------------------------------
# Added 2026-10-20 at Eric's request: "you can add the twitter and cardono
# comments to the comment archive. expand it to include cases like that."
#
# The X material is the same kind as the LinkedIn lane and sometimes better —
# Kevin Payne's replies to Eric ("Metrics outlive principles. Once the dashboard
# rewards extraction, the people who remember why the company worked stop getting
# promoted") are sharper than most of what the LinkedIn sweep returns. Engagement
# is deliberately not a gate: these feed social posts, not the timeline, so a
# zero-like reply with a great sentence is worth more than a popular "congrats!".
#
# "Cases like that" also widens what qualifies beyond superlatives, to any
# observation that uses the book's argument. That judgment stays in the cron turn
# — this file only decides what is worth a human look.

ERIC_HANDLES = {"ericries", "ericriesactual"}


def _twitter_author(a: dict | None) -> dict:
    a = a or {}
    return {
        "name": a.get("name") or a.get("userName") or "",
        "headline": a.get("description") or "",
        "profile_url": a.get("url") or (f"https://x.com/{a['userName']}" if a.get("userName") else None),
        "followers": a.get("followers"),
    }


def _twitter_date(raw: str | None) -> str | None:
    """Twitter's "Tue Oct 20 23:02:09 +0000 2026" to ISO, or the raw value back.

    Never drop a record over a date: the text is the thing being archived.
    """
    if not raw:
        return None
    try:
        return datetime.datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y").isoformat()
    except (ValueError, TypeError):
        return raw


def queue_from_tweets(items: list[dict], *, scan_source: str, seen: set[str]) -> list[dict]:
    """Anchor-passing tweets, in the same queue shape as the LinkedIn path."""
    by_id = {str(t.get("id")): t for t in items if t.get("id")}
    out: list[dict] = []
    for t in items:
        if t.get("isRetweet"):
            continue
        author = t.get("author") or {}
        if (author.get("userName") or "").lower() in ERIC_HANDLES:
            continue          # Eric's own posts are never archive candidates
        text = (t.get("text") or t.get("fullText") or "").strip()
        if not text:
            continue

        # A reply to Eric inherits the book context exactly as a comment on his
        # LinkedIn feed does — his best repliers never name the book.
        anchored = (
            BOOK_ANCHOR_RE.search(text)
            or (t.get("inReplyToUsername") or "").lower() in ERIC_HANDLES
        )
        if not anchored:
            continue

        ident = f"tweet:{t.get('id')}"
        if ident in seen:
            continue

        parent = by_id.get(str(t.get("inReplyToId") or t.get("conversationId") or ""))
        parent_meta = None
        if parent is not None and str(parent.get("id")) != str(t.get("id")):
            parent_meta = {
                "text": (parent.get("text") or parent.get("fullText") or "").strip(),
                "permalink": parent.get("url") or parent.get("twitterUrl"),
                "author": _twitter_author(parent.get("author")),
            }

        out.append({
            "identifier": ident,
            "platform": "twitter",
            "kind": "comment",
            "source_scan": scan_source,
            "text": text,
            "permalink": t.get("url") or t.get("twitterUrl"),
            "posted_at": _twitter_date(t.get("createdAt")),
            "reactions": t.get("likeCount"),
            "comments_count": t.get("replyCount"),
            "author": _twitter_author(author),
            "parent_post": parent_meta,
        })
    return out


def normalize_post_meta(post: dict) -> dict:
    """A compact snapshot of a post for use as parent_post context on a comment record."""
    return {
        "author": _author_from(post.get("author") or post.get("actor")),
        "permalink": _post_permalink(post),
        "content_preview": ((post.get("content") or post.get("commentary") or "")[:240]).strip(),
    }


def _load_seen_identifiers() -> set[str]:
    """Return every `identifier` present in any archive file so far, so the
    same post/comment isn't re-captured on a later scan."""
    seen: set[str] = set()
    for f in ARCHIVE_DIR.glob("*.json"):
        # Skip hidden files (e.g. .llm-queue.json — that's the pending-classification
        # queue, not archived records)
        if f.name.startswith("."):
            continue
        try:
            for r in json.loads(f.read_text()):
                ident = r.get("identifier")
                if ident:
                    seen.add(ident)
        except Exception:
            pass
    return seen


def _apply_verdicts_mode(verdicts_path: Path) -> int:
    """Second-pass entry point. Read a JSON list of LLM verdicts from Claude's
    cron turn and append them to today's archive as `<llm>`-flagged records.

    Verdict schema (each item):
      {
        "identifier": "comment:1234567" or "activity:1234567" or "post:...",
        "kind": "post" | "comment",
        "source_scan": "linkedin-keyword" | "linkedin-author-eries",
        "text": "<full text of the item>",
        "pull_quote": "<verbatim short pull-quote, <=360 chars>",
        "permalink": "https://linkedin.com/...",
        "posted_at": "2026-09-24T..." (or null),
        "reactions": 12 (or null),
        "comments_count": 3 (or null),
        "author": {"name": "...", "headline": "...", "profile_url": "..."},
        "parent_post": {...} | null
      }
    """
    verdicts = json.loads(verdicts_path.read_text())
    if not isinstance(verdicts, list):
        print("verdicts JSON must be a list", file=sys.stderr)
        return 2

    known_urls = _load_known_source_urls()
    known_names = _load_known_author_names()
    seen_identifiers = _load_seen_identifiers()

    today = datetime.date.today().isoformat()
    archive_path = ARCHIVE_DIR / f"{today}.json"
    existing: list[dict] = json.loads(archive_path.read_text()) if archive_path.exists() else []

    added = 0
    skipped_seen = 0
    skipped_short = 0
    for v in verdicts:
        ident = v.get("identifier")
        text = v.get("text") or ""
        if not ident or not text:
            continue
        if ident in seen_identifiers:
            skipped_seen += 1
            continue
        substantive = _substantive_text(text)
        if len(substantive) < 12:
            skipped_short += 1
            continue
        quote = (v.get("pull_quote") or "").strip() or _sentence_span_containing(text, "")[:360]
        author = v.get("author") or {}
        rec = {
            "captured_at": (datetime.datetime.now(datetime.UTC)
                            .replace(microsecond=0, tzinfo=None).isoformat() + "Z"),
            "source_scan": v.get("source_scan") or "unknown",
            # Added 2026-10-20 when the archive gained Twitter/X. Records written
            # before that have no platform key; readers should default to
            # "linkedin", which is what every one of them is.
            "platform": v.get("platform") or "linkedin",
            "item_kind": v.get("kind") or "comment",
            "identifier": ident,
            "superlative_matches": ["<llm>"],
            "full_text": text,
            "pull_quote": quote,
            "quotes_the_book": False,
            "has_emoji": has_emoji(text),
            "low_confidence": len(substantive) < 40,
            "already_have": _already_have(
                v.get("permalink"), author.get("name"),
                known_urls, known_names,
            ),
            "author": author,
            "permalink": v.get("permalink"),
            "posted_at": v.get("posted_at"),
            "reactions": v.get("reactions"),
            "comments_count": v.get("comments_count"),
            "parent_post": v.get("parent_post"),
        }
        seen_identifiers.add(ident)
        existing.append(rec)
        added += 1

    archive_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    # Clear the queue file after applying.
    if LLM_QUEUE_PATH.exists():
        LLM_QUEUE_PATH.unlink()
    print(
        f"Applied {added} LLM-verified records (skipped: seen={skipped_seen}, "
        f"short={skipped_short}) to {_rel(archive_path)}. "
        f"Queue cleared."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?",
                    help="Path to Apify scan JSON (post items array). Omit when using --apply-verdicts.")
    ap.add_argument("--scan-source", default="unknown",
                    help="Label for this scan (e.g. linkedin-keyword, linkedin-author-eries)")
    ap.add_argument("--platform", default="linkedin", choices=["linkedin", "twitter"],
                    help="Input shape: harvestapi LinkedIn posts, or apidojo tweets.")
    ap.add_argument("--apply-verdicts", metavar="PATH",
                    help="Second-pass mode: read a JSON list of LLM verdicts from Claude's cron turn and append them as <llm>-flagged records.")
    args = ap.parse_args()

    if args.apply_verdicts:
        return _apply_verdicts_mode(Path(args.apply_verdicts))

    if not args.input:
        ap.error("input JSON is required unless --apply-verdicts is used")

    data = json.loads(Path(args.input).read_text())
    items = data if isinstance(data, list) else data.get("items", [])

    known_urls = _load_known_source_urls()
    known_names = _load_known_author_names()
    seen_identifiers = _load_seen_identifiers()

    today = datetime.date.today().isoformat()
    archive_path = ARCHIVE_DIR / f"{today}.json"
    existing: list[dict] = []
    if archive_path.exists():
        existing = json.loads(archive_path.read_text())

    if args.platform == "twitter":
        llm_queue = queue_from_tweets(items, scan_source=args.scan_source, seen=seen_identifiers)
        print(f"Scanned {len(items)} tweets.")
    else:
        llm_queue = queue_from_posts(items, scan_source=args.scan_source, seen=seen_identifiers,
                                     verbose=True)

    return _persist_queue(llm_queue)


def queue_from_posts(items: list[dict], *, scan_source: str, seen: set[str],
                     verbose: bool = False) -> list[dict]:
    """Anchor-passing LinkedIn posts and comments, as queue records."""
    scanned_posts = 0
    scanned_comments = 0
    llm_queue: list[dict] = []
    for post in items:
        scanned_posts += 1
        scanned_comments += len(post.get("comments") or [])

        post_text = post.get("content") or post.get("commentary") or ""
        if post_text and BOOK_ANCHOR_RE.search(post_text):
            permalink = _post_permalink(post)
            kind = "comment" if permalink and "commentUrn=" in permalink else "post"
            ident = _stable_identifier(
                kind=kind, permalink=permalink,
                raw_id=_get(post, "id", "postId", "entityId"),
            )
            if ident and ident not in seen:
                llm_queue.append({
                    "identifier": ident,
                    "platform": "linkedin",
                    "kind": kind,
                    "source_scan": scan_source,
                    "text": post_text,
                    "permalink": permalink,
                    "posted_at": (post.get("postedAt") or {}).get("date") or post.get("createdAt"),
                    "reactions": (post.get("engagement") or {}).get("likes"),
                    "comments_count": (post.get("engagement") or {}).get("comments"),
                    "author": _author_from(post.get("author") or post.get("actor")),
                    "parent_post": None,
                })

        for cmt in post.get("comments") or []:
            ctext = cmt.get("commentary") or cmt.get("text") or ""
            # Comments on Eric's OWN feed inherit book context from the parent.
            # On keyword scans, comments under a book-anchored parent post also
            # inherit anchor. Otherwise, the comment itself must name the book.
            comment_anchor = (
                BOOK_ANCHOR_RE.search(ctext)
                or scan_source.startswith("linkedin-author-eries")
                or BOOK_ANCHOR_RE.search(post_text or "")
            )
            if ctext and comment_anchor:
                cmt_permalink = _comment_permalink(cmt)
                ident = _stable_identifier(
                    kind="comment", permalink=cmt_permalink,
                    raw_id=_get(cmt, "id", "urn"),
                )
                if ident and ident not in seen:
                    llm_queue.append({
                        "identifier": ident,
                        "platform": "linkedin",
                        "kind": "comment",
                        "source_scan": scan_source,
                        "text": ctext,
                        "permalink": cmt_permalink,
                        "posted_at": cmt.get("createdAt") or (cmt.get("postedAt") or {}).get("date"),
                        "reactions": (cmt.get("engagement") or {}).get("likes"),
                        "comments_count": (cmt.get("engagement") or {}).get("comments"),
                        "author": _author_from(cmt.get("actor") or cmt.get("author")),
                        "parent_post": normalize_post_meta(post),
                    })

    if verbose:
        print(f"Scanned {scanned_posts} posts / {scanned_comments} comments.")
    return llm_queue


def _persist_queue(llm_queue: list[dict]) -> int:
    """Merge new candidates into the pending queue for the cron-turn second pass."""
    existing_queue: list[dict] = []
    if LLM_QUEUE_PATH.exists():
        try:
            existing_queue = json.loads(LLM_QUEUE_PATH.read_text())
        except Exception:
            existing_queue = []
    # Dedup queue by identifier across both scan sources.
    seen_q = {q.get("identifier") for q in existing_queue if q.get("identifier")}
    merged_queue = existing_queue + [q for q in llm_queue if q.get("identifier") and q["identifier"] not in seen_q]
    LLM_QUEUE_PATH.write_text(json.dumps(merged_queue, indent=2, ensure_ascii=False))
    if merged_queue:
        print(
            f"LLM queue: {len(llm_queue)} new candidates added ({len(merged_queue)} total pending). "
            f"Claude should now classify {_rel(LLM_QUEUE_PATH)} and re-run with "
            f"--apply-verdicts <path-to-verdicts.json>."
        )
    else:
        print("LLM queue empty (no anchor-passing candidates without regex hits).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
