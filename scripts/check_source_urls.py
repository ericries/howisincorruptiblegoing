#!/usr/bin/env python3
"""Fail a LinkedIn URL that does not match the one in the raw archive.

The activity id is the canonical part of a LinkedIn post URL — the slug is
decorative and the trailing token is opaque. So if an id appears in a raw
archive, the full URL is knowable, and any difference means the URL was typed
rather than copied.

This exists because typing one is exactly what happened twice in two days:
a tweet URL ending in `/status/` with no id (2026-11-03) and a Burka follow-up
whose slug and activity id were both invented (2026-11-04). Both were caught by
hand, one of them only because I went back to check. Being careful is not a
mechanism; this is.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "archive" / "linkedin-raw"

_ACTIVITY = re.compile(r"activity[-:](\d{10,})", re.I)
_LINKEDIN_POST = re.compile(r"linkedin\.com/posts/", re.I)


_CACHE: dict[Path, dict[str, str]] = {}


def _archived_by_id(raw_dir: Path) -> dict[str, str]:
    """activity id -> the URL exactly as the actor reported it.

    Cached per directory: the first version rebuilt the whole index for every
    entry, which is fine for the handful the hook passes and quadratic over
    the full 900.
    """
    if raw_dir in _CACHE:
        return _CACHE[raw_dir]
    out: dict[str, str] = {}
    if not raw_dir.is_dir():
        return out
    for path in sorted(raw_dir.glob("*.json")):
        try:
            rows = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        items = rows if isinstance(rows, list) else rows.get("items", [])
        for r in items:
            if not isinstance(r, dict):
                continue
            url = str(r.get("linkedinUrl") or r.get("url") or "")
            # Index ONLY canonical post URLs. A comment permalink
            # (/feed/update/...?commentUrn=) embeds its PARENT post's activity
            # id, so indexing one makes every correct /posts/ URL for that post
            # look fabricated — 33 of them on the first run.
            if not _LINKEDIN_POST.search(url):
                continue
            m = _ACTIVITY.search(url)
            if m:
                out.setdefault(m.group(1), url)
    _CACHE[raw_dir] = out
    return out


def check_urls(urls, raw_dir: Path = RAW_DIR) -> list[tuple[str, str]]:
    """Return [(written, archived)] for every URL that contradicts the archive."""
    archived = _archived_by_id(raw_dir)
    bad = []
    for u in urls:
        if not u or not _LINKEDIN_POST.search(str(u)):
            continue
        m = _ACTIVITY.search(str(u))
        if not m:
            continue
        real = archived.get(m.group(1))
        if real and real != u:
            bad.append((u, real))
    return bad


def urls_in(entry: dict) -> list[str]:
    urls = [entry.get("source_url")]
    for s in entry.get("source_urls") or []:
        urls.append(s.get("url") if isinstance(s, dict) else s)
    return [u for u in urls if u]


def main(argv: list[str]) -> int:
    failures = 0
    for arg in argv:
        p = Path(arg)
        if not p.is_file():
            continue
        try:
            entry = json.loads(p.read_text())
        except ValueError:
            continue
        for written, real in check_urls(urls_in(entry)):
            failures += 1
            print(f"❌ {p.name}\n   written : {written}\n   archived: {real}")
    if failures:
        print(f"\nSource-url integrity: {failures} URL(s) contradict the raw archive. "
              f"Copy the URL from the dataset; do not retype it.")
        return 1
    print(f"Source-url integrity: OK ({len(argv)} entr(ies) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
