#!/usr/bin/env python3
"""
scripts/archive-linkedin-superlatives.py

Reads an Apify LinkedIn scan output (JSON: array of posts with `comments` when
scrapeComments=true was passed) and filters comments for superlative praise of
Incorruptible. Appends matches to data/archive/linkedin-comments/YYYY-MM-DD.json.

Local-only archive (gitignored) — never pushed to the site. Intended for social-
media reuse later.

Usage:
  python3 scripts/archive-linkedin-superlatives.py <scan.json> [--scan-source=name]

The input file is expected to be either an array of post items OR the wrapped
Apify shape {items: [...]}.
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

SUPERLATIVE_PATTERNS = [
    r"best book of the (year|decade|century|our (lifetime|generation)|all time|ever)",
    r"best (business|leadership|management|startup) book (i(?:'ve| have)? (?:ever )?read|of \d{4}|of the (year|decade))",
    r"one of the (best|greatest|most important) books",
    r"life[\s-]?chang(?:ing|ed)",
    r"chang(?:ed|es|ing) my life",
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
    # more relaxed but still superlative-tier:
    r"great read",
    r"brilliant (book|read)",
    r"wonderful (book|read)",
    r"excellent (book|read)",
    r"absolutely (love|loved|loving|brilliant)",
    r"loved (this|the) book",
    r"can(?:'t| ?not) wait to (read|dive)",
    # 4+ consecutive star emojis, tolerating the U+FE0F variation selector
    r"(?:⭐️?|🌟️?){4,}",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in SUPERLATIVE_PATTERNS]


def find_matches(text: str) -> list[str]:
    """Return the unique superlative phrases matched in `text`."""
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


def _get(d: dict, *keys):
    for k in keys:
        if d and k in d and d[k] is not None:
            return d[k]
    return None


def normalize_post(post: dict) -> dict:
    # harvestapi uses `author` for keyword search, `actor` for author-feed scrape
    author = post.get("author") or post.get("actor") or {}
    posted = post.get("postedAt") or {}
    return {
        "id": _get(post, "postId", "id", "entityId"),
        "url": _get(post, "linkedinUrl", "url"),
        "posted_at": posted.get("date") or post.get("createdAt"),
        "author": {
            "name": author.get("name"),
            "linkedinUrl": author.get("linkedinUrl"),
            "info": author.get("info") or author.get("position"),
        },
        "content_preview": ((post.get("content") or post.get("commentary") or "")[:240]).strip(),
    }


def normalize_comment(cmt: dict) -> dict:
    # comment fields: `commentary` (text), `actor` (commenter), `engagement`, `createdAt`
    author = cmt.get("actor") or cmt.get("author") or {}
    engagement = cmt.get("engagement") or {}
    return {
        "id": _get(cmt, "id", "urn"),
        "text": _get(cmt, "commentary", "text", "content"),
        "author": {
            "name": author.get("name"),
            "linkedinUrl": author.get("linkedinUrl"),
            "info": author.get("position") or author.get("info"),
        },
        "likes": engagement.get("likes") if engagement else cmt.get("likes"),
        "posted_at": cmt.get("createdAt") or ((cmt.get("postedAt") or {}).get("date")),
    }


def dedupe_key(rec: dict) -> str:
    # LinkedIn comment IDs are globally unique — same post can have different
    # post.id representations across scans (author-feed vs keyword search) so
    # keying on comment.id alone is more robust.
    return rec["comment"]["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to Apify scan JSON (post items array)")
    ap.add_argument("--scan-source", default="unknown",
                    help="Label for this scan (e.g. linkedin-keyword, linkedin-author-eries)")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text())
    items = data if isinstance(data, list) else data.get("items", [])

    today = datetime.date.today().isoformat()
    archive_path = ARCHIVE_DIR / f"{today}.json"
    existing: list[dict] = []
    if archive_path.exists():
        existing = json.loads(archive_path.read_text())
    seen_keys = {dedupe_key(r) for r in existing}

    new_records: list[dict] = []
    scanned_posts = 0
    scanned_comments = 0
    for post in items:
        scanned_posts += 1
        comments = post.get("comments") or []
        for cmt in comments:
            scanned_comments += 1
            text = cmt.get("commentary") or cmt.get("text") or cmt.get("content") or ""
            matches = find_matches(text)
            if not matches:
                continue
            rec = {
                "captured_at": datetime.datetime.now(datetime.UTC).replace(microsecond=0, tzinfo=None).isoformat() + "Z",
                "source_scan": args.scan_source,
                "superlative_matches": matches,
                "post": normalize_post(post),
                "comment": normalize_comment(cmt),
            }
            key = dedupe_key(rec)
            if not rec["comment"]["id"] or key in seen_keys:
                continue
            seen_keys.add(key)
            new_records.append(rec)

    if new_records:
        merged = existing + new_records
        archive_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        print(f"Scanned {scanned_posts} posts / {scanned_comments} comments. "
              f"Archived {len(new_records)} new superlative comments to "
              f"{archive_path.relative_to(ROOT)}")
    else:
        print(f"Scanned {scanned_posts} posts / {scanned_comments} comments. "
              f"No new superlative matches (archive: {archive_path.relative_to(ROOT)}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
