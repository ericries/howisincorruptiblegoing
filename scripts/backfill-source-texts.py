#!/usr/bin/env python3
"""Fill data/archive/source-texts/ from whatever raw scrapes we still hold locally.

The site publishes an excerpt; this keeps the whole thing. Sources swept, in
order of directness:

  1. data/archive/transcripts/<entry-id>.txt     — already keyed by entry id
  2. data/archive/linkedin-comments/*.json       — permalink -> full_text
  3. data/{goodreads-reviews,archive/goodreads}/ — shelving.webUrl -> review text
  4. data/archive/{linkedin,twitter}-raw/*.json  — post url -> content

Anything we no longer hold locally stays uncaptured and is listed by --report;
those need a re-fetch, which this script deliberately does not do (no network).

Usage:
  python3 scripts/backfill-source-texts.py            # capture what we can
  python3 scripts/backfill-source-texts.py --report   # coverage only, no writes
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import source_texts  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ENTRIES = REPO / "content" / "entries"


def norm_url(u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip().split("?")[0].rstrip("/")
    return u.replace("http://", "https://").replace("://linkedin.com", "://www.linkedin.com")


def strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</p>\s*<p>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_url_index() -> dict[str, dict]:
    """url -> {text, author, platform} from every local raw archive."""
    idx: dict[str, dict] = {}

    def add(url, text, author=None, platform=None):
        u = norm_url(url)
        if not u or not (text or "").strip():
            return
        # keep the longest text seen for a url
        if u not in idx or len(text) > len(idx[u]["text"]):
            idx[u] = {"text": text, "author": author, "platform": platform}

    for f in (REPO / "data/archive/linkedin-comments").glob("*.json"):
        if f.name.startswith("."):
            continue
        for r in load_json(f) or []:
            # A comment's permalink carries ?commentUrn= and normalises down to
            # its parent post's URL — indexing it would file the comment's text
            # as if it were the post. Posts only.
            if r.get("item_kind") != "post":
                continue
            add(r.get("permalink"), r.get("full_text"),
                (r.get("author") or {}).get("name"), "linkedin")

    for d in ("data/goodreads-reviews", "data/archive/goodreads"):
        for f in (REPO / d).glob("*.json"):
            for r in load_json(f) or []:
                if not isinstance(r, dict):
                    continue
                add((r.get("shelving") or {}).get("webUrl"), strip_html(r.get("text") or ""),
                    (r.get("creator") or {}).get("name"), "goodreads")

    for d in ("data/archive/linkedin-raw", "data/archive/twitter-raw"):
        for f in (REPO / d).glob("*.json"):
            for r in load_json(f) or []:
                if not isinstance(r, dict):
                    continue
                add(r.get("linkedinUrl"), r.get("content"),
                    (r.get("author") or {}).get("name"), "linkedin")
                add(r.get("url") or r.get("twitterUrl"), r.get("fullText") or r.get("text"),
                    (r.get("author") or {}).get("name"), "twitter")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="coverage only, no writes")
    ap.add_argument("--audit", action="store_true",
                    help="list entries whose published blockquote is not found verbatim "
                         "in the stored source (transcripts excluded — ASR is cleaned by design)")
    args = ap.parse_args()

    if args.audit:
        drift = []
        for f in sorted(ENTRIES.glob("*.json")):
            e = load_json(f) or {}
            eid, bq = e.get("id"), e.get("blockquote")
            rec = source_texts.load(eid) if eid else None
            if not rec or not bq or rec.get("platform") == "transcript":
                continue
            # Only compare when the stored text came from the URL the blockquote
            # is attributed to. Entries often list a secondary source_urls[] link
            # whose text we happen to hold; that is not the quote's origin.
            if norm_url(rec.get("source_url")) != norm_url(e.get("source_url")):
                continue
            if not source_texts.contains_blockquote(eid, bq):
                drift.append(eid)
        print(f"Blockquotes not found verbatim in the stored source: {len(drift)}")
        for d in drift:
            print("   ", d)
        print("\n(Each needs a human look: usually a dropped emoji, a smart-quote "
              "swap, or a quote assembled across non-contiguous paragraphs.)")
        return 0

    entries = sorted(
        (load_json(f) for f in ENTRIES.glob("*.json")),
        key=lambda e: (e or {}).get("date", ""),
    )
    entries = [e for e in entries if e]

    idx = build_url_index()
    transcripts = REPO / "data/archive/transcripts"

    captured = {"transcript": 0, "url-index": 0}
    already = 0

    for e in entries:
        eid = e.get("id")
        if not eid:
            continue
        try:
            if source_texts.has(eid):
                already += 1
                continue
        except ValueError:
            continue

        text = author = platform = matched_url = None

        t = transcripts / f"{eid}.txt"
        if t.exists():
            text, platform, kind = t.read_text(encoding="utf-8"), "transcript", "transcript"
            matched_url = e.get("source_url")
        else:
            urls = [e.get("source_url")] + [
                s.get("url") for s in (e.get("source_urls") or []) if isinstance(s, dict)
            ]
            matched_url = None
            for u in urls:
                hit = idx.get(norm_url(u))
                if hit:
                    text, author, platform, kind = (
                        hit["text"], hit["author"], hit["platform"], "url-index")
                    matched_url = u
                    break

        if not (text or "").strip():
            continue
        if not args.report:
            source_texts.capture(
                eid,
                source_url=matched_url or e.get("source_url") or "",
                full_text=text,
                author=author or e.get("attribution"),
                platform=platform,
            )
        captured[kind] += 1

    total = len(entries)
    have = already + sum(captured.values())
    missing = [e["id"] for e in entries if e.get("id") and not source_texts.has(e["id"])]

    verb = "would capture" if args.report else "captured"
    print(f"Entries: {total}")
    print(f"  already had full source : {already}")
    print(f"  {verb} from transcripts  : {captured['transcript']}")
    print(f"  {verb} from raw archives : {captured['url-index']}")
    print(f"  still missing           : {len(missing)}  ({100*have//total if total else 0}% covered)")
    if missing:
        print("\nNo local raw scrape held for (newest 15):")
        for m in missing[-15:]:
            print("   ", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
