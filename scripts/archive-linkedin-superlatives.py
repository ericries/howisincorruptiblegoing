#!/usr/bin/env python3
"""
scripts/archive-linkedin-superlatives.py

Reads an Apify harvestapi/linkedin-post-search output (JSON: array of posts,
optionally with `comments` arrays when scrapeComments=true) and filters BOTH
post bodies AND comment text for superlative praise of Incorruptible. Appends
matches to data/archive/linkedin-comments/YYYY-MM-DD.json.

Local-only archive (gitignored) — never pushed to the site. Downstream: the
social-media agent turns these into quote cards + schedules them via Buffer.

Schema per record is documented in
  data/archive/linkedin-comments/FORMAT-NOTES.md
and reference_linkedin_comment_archive.md in memory.

Usage:
  python3 scripts/archive-linkedin-superlatives.py <scan.json> [--scan-source=name]
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

SUPERLATIVE_PATTERNS = [
    r"best book of the (year|decade|century|our (lifetime|generation)|all time|ever)",
    r"best (business|leadership|management|startup) book (i(?:'ve| have)? (?:ever )?read|of \d{4}|of the (year|decade))",
    r"one of the (best|greatest|most important) books",
    r"life[\s-]?chang(?:ing|ed)",
    r"chang(?:ed|es|ing) my life",
    r"changed my perspective",
    r"must[\s-]?read",
    r"a must[\s-]?read",
    r"the most important book",
    r"masterpiece",
    r"essential reading",
    r"phenomenal",
    r"extraordinary",
    r"mind[\s-]?blow(?:ing|n)",
    r"eye[\s-]?open(?:ing|er)",
    r"revolutionary",
    r"profound(?:ly)?",
    r"greatest (business|leadership|management) book",
    r"the book of the year",
    r"5[\s-]?star",
    r"five[\s-]?stars?",
    r"⭐⭐⭐⭐⭐",
    r"(?:⭐️?|🌟️?){4,}",  # 4+ star emojis (with/without variation selector)
    r"can(?:'t| ?not) recommend (this |it |enough)",
    r"highest recommendation",
    r"changed how i think",
    r"read it in one sitting",
    r"couldn'?t put (it |this )?down",
    r"insanely great",
    r"the single most important",
    r"blew my mind",
    r"most important business book",
    r"instantly a classic",
    r"great read",
    r"brilliant (book|read)",
    r"wonderful (book|read)",
    r"excellent (book|read)",
    r"absolutely (love|loved|loving|brilliant)",
    r"loved (this|the) book",
    r"can(?:'t| ?not) wait to (read|dive)",
    r"super insightful",
    r"the (real |actual )?playbook",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in SUPERLATIVE_PATTERNS]

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

# Heuristic: "they are quoting the book" if the matched phrase sits inside
# quotation marks AND the author uses an attribution word for the book/author
# somewhere in the text.
BOOK_ATTRIBUTION_WORDS = re.compile(
    r"\b(ries|incorruptible|the book|he (says|writes)|from the book|book's line|the book's)\b",
    re.IGNORECASE,
)
QUOTE_MARK_RE = re.compile(r"[\"“”'‘’„«»]")


def find_matches(text: str) -> list[str]:
    """Return the unique superlative phrases matched in `text` (in order of first occurrence)."""
    if not text:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    for pat in COMPILED:
        for m in pat.finditer(text):
            phrase = m.group(0)
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                hits.append(phrase)
    return hits


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


def guess_pull_quote(text: str, matches: list[str]) -> str:
    """The single strongest contiguous sentence for the card.

    Prefer the sentence containing the FIRST superlative match, capped to a
    reasonable single-card length (~360 chars). The downstream agent will
    verify against `full_text` before publishing.
    """
    if not text or not matches:
        return ""
    sentence = _sentence_span_containing(text, matches[0])
    if not sentence:
        return ""
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if len(sentence) > 360:
        sentence = sentence[:357].rstrip() + "…"
    return sentence


def quotes_the_book(text: str, matches: list[str]) -> bool:
    """Heuristic: is the matched phrase the author quoting the book, vs. their own words?

    True when the sentence-span containing the match is itself wrapped in
    quotation marks (single or curly), OR when the surrounding text uses an
    explicit attribution word (Ries / Incorruptible / from the book / etc.)
    within 120 chars of the match.
    """
    if not text or not matches:
        return False
    span = _sentence_span_containing(text, matches[0])
    if QUOTE_MARK_RE.search(span or ""):
        # a quoted sentence is a strong signal
        if BOOK_ATTRIBUTION_WORDS.search(text):
            return True
    # also true when the exact matched phrase sits inside quote marks nearby
    for m in matches:
        idx = text.lower().find(m.lower())
        if idx < 0:
            continue
        pre = text[max(0, idx - 30):idx]
        post = text[idx + len(m):idx + len(m) + 30]
        if QUOTE_MARK_RE.search(pre) and QUOTE_MARK_RE.search(post):
            if BOOK_ATTRIBUTION_WORDS.search(text):
                return True
    return False


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


# ---- quality gate ----

def _quality_verdict(full_text: str, matches: list[str]) -> tuple[bool, bool]:
    """Return (should_store, low_confidence).

    Measures the SUBSTANTIVE text (URLs and emoji stripped) so that
    "Great read ⭐️⭐️⭐️⭐️⭐️ https://…/incorruptible" is correctly rejected as
    a one-liner. Rough bar: at least one contiguous sentence of real praise.
    """
    text = (full_text or "").strip()
    substantive = _substantive_text(text)
    if len(substantive) < 40:
        # after removing URLs + emoji, essentially just the matched phrase
        return False, False
    sentence = _sentence_span_containing(text, matches[0]) if matches else text
    sub_sentence = _substantive_text(sentence)
    if len(sub_sentence) < 40 and len(substantive) < 90:
        return False, False
    low_conf = len(substantive) < 90 or len(sub_sentence) < 60
    return True, low_conf


# ---- record building ----

def _matched_record(*, kind: str, source_scan: str, matches: list[str],
                    text: str, permalink: str | None, posted_at: str | None,
                    reactions: int | None, comments_count: int | None,
                    author: dict, parent_post: dict | None,
                    identifier: str | None,
                    known_urls: set[str], known_names: set[str]) -> dict | None:
    should, low_conf = _quality_verdict(text, matches)
    if not should:
        return None
    return {
        "captured_at": (datetime.datetime.now(datetime.UTC)
                        .replace(microsecond=0, tzinfo=None).isoformat() + "Z"),
        "source_scan": source_scan,
        "item_kind": kind,  # "post" or "comment"
        "identifier": identifier,  # LinkedIn post.id or comment.id for dedupe
        "superlative_matches": matches,
        "full_text": text,
        "pull_quote": guess_pull_quote(text, matches),
        "quotes_the_book": quotes_the_book(text, matches),
        "has_emoji": has_emoji(text),
        "low_confidence": low_conf,
        "already_have": _already_have(permalink, author.get("name"),
                                       known_urls, known_names),
        "author": author,
        "permalink": permalink,
        "posted_at": posted_at,
        "reactions": reactions,
        "comments_count": comments_count,
        "parent_post": parent_post,  # non-null only when item_kind == "comment"
    }


def normalize_post_meta(post: dict) -> dict:
    """A compact snapshot of a post for use as parent_post context on a comment record."""
    return {
        "author": _author_from(post.get("author") or post.get("actor")),
        "permalink": _post_permalink(post),
        "content_preview": ((post.get("content") or post.get("commentary") or "")[:240]).strip(),
    }


# ---- main iteration ----

def _iter_items(post: dict, source_scan: str,
                known_urls: set[str], known_names: set[str]):
    """Yield archive records for a single post + its comments."""
    # POST body (or — occasionally — a comment that harvestapi surfaces as a
    # top-level item in an author-feed scrape; detect via commentUrn in URL)
    post_text = post.get("content") or post.get("commentary") or ""
    post_matches = find_matches(post_text)
    if post_matches:
        permalink = _post_permalink(post)
        kind = "comment" if permalink and "commentUrn=" in permalink else "post"
        rec = _matched_record(
            kind=kind,
            source_scan=source_scan,
            matches=post_matches,
            text=post_text,
            permalink=permalink,
            posted_at=(post.get("postedAt") or {}).get("date") or post.get("createdAt"),
            reactions=(post.get("engagement") or {}).get("likes"),
            comments_count=(post.get("engagement") or {}).get("comments"),
            author=_author_from(post.get("author") or post.get("actor")),
            parent_post=None,
            identifier=_stable_identifier(
                kind=kind, permalink=permalink,
                raw_id=_get(post, "id", "postId", "entityId"),
            ),
            known_urls=known_urls,
            known_names=known_names,
        )
        if rec:
            yield rec

    # COMMENTS
    for cmt in post.get("comments") or []:
        text = cmt.get("commentary") or cmt.get("text") or ""
        c_matches = find_matches(text)
        if not c_matches:
            continue
        author = _author_from(cmt.get("actor") or cmt.get("author"))
        cmt_permalink = _comment_permalink(cmt)
        rec = _matched_record(
            kind="comment",
            source_scan=source_scan,
            matches=c_matches,
            text=text,
            permalink=cmt_permalink,
            posted_at=cmt.get("createdAt") or (cmt.get("postedAt") or {}).get("date"),
            reactions=(cmt.get("engagement") or {}).get("likes"),
            comments_count=(cmt.get("engagement") or {}).get("comments"),
            author=author,
            parent_post=normalize_post_meta(post),
            identifier=_stable_identifier(
                kind="comment", permalink=cmt_permalink,
                raw_id=_get(cmt, "id", "urn"),
            ),
            known_urls=known_urls,
            known_names=known_names,
        )
        if rec:
            yield rec


def _load_seen_identifiers() -> set[str]:
    """Return every `identifier` present in any archive file so far, so the
    same post/comment isn't re-captured on a later scan."""
    seen: set[str] = set()
    for f in ARCHIVE_DIR.glob("*.json"):
        try:
            for r in json.loads(f.read_text()):
                ident = r.get("identifier")
                if ident:
                    seen.add(ident)
        except Exception:
            pass
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to Apify scan JSON (post items array)")
    ap.add_argument("--scan-source", default="unknown",
                    help="Label for this scan (e.g. linkedin-keyword, linkedin-author-eries)")
    args = ap.parse_args()

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

    new_records: list[dict] = []
    scanned_posts = 0
    scanned_comments = 0
    for post in items:
        scanned_posts += 1
        scanned_comments += len(post.get("comments") or [])
        for rec in _iter_items(post, args.scan_source, known_urls, known_names):
            ident = rec.get("identifier")
            if not ident or ident in seen_identifiers:
                continue
            seen_identifiers.add(ident)
            new_records.append(rec)

    if new_records:
        merged = existing + new_records
        archive_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        # count kinds for a slightly more useful print line
        n_posts = sum(1 for r in new_records if r.get("item_kind") == "post")
        n_cmts = sum(1 for r in new_records if r.get("item_kind") == "comment")
        n_dupes = sum(1 for r in new_records if r.get("already_have"))
        n_low = sum(1 for r in new_records if r.get("low_confidence"))
        print(
            f"Scanned {scanned_posts} posts / {scanned_comments} comments. "
            f"Archived {len(new_records)} new superlative items "
            f"(posts={n_posts}, comments={n_cmts}, already_have={n_dupes}, "
            f"low_confidence={n_low}) to {archive_path.relative_to(ROOT)}"
        )
    else:
        print(
            f"Scanned {scanned_posts} posts / {scanned_comments} comments. "
            f"No new superlative items (archive: {archive_path.relative_to(ROOT)})."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
