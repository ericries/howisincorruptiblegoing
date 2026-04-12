#!/usr/bin/env python3
"""Verify that each entry's blockquote text appears at its source_url.

Usage:
    python scripts/review_bot/verify_quotes.py content/entries/file1.json ...

Warns (but does not fail) if the URL is unreachable.
Exits 1 if a quote is NOT found on a reachable page.
"""

import json
import os
import re
import sys

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch URL and return text content, or None if unreachable."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; IncorruptibleReviewBot/1.0; "
            "+https://github.com/ericries/howisincorruptiblegoing)"
        )
    }
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.text
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return None


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> int:
    changed_files = sys.argv[1:]

    if not changed_files:
        print("No entry files specified — nothing to verify.")
        return 0

    has_failures = False

    for filepath in changed_files:
        if not os.path.isfile(filepath):
            print(f"WARN  File not found: {filepath} — skipping")
            continue

        try:
            with open(filepath, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN  Could not read {filepath}: {exc} — skipping")
            continue

        source_url = data.get("source_url", "")
        blockquote = data.get("blockquote", "")

        if not source_url or not blockquote:
            print(f"WARN  {filepath}: missing source_url or blockquote — skipping")
            continue

        print(f"Checking quote for {filepath} ...")
        page_content = fetch_page(source_url)

        if page_content is None:
            print(f"WARN  Could not fetch {source_url} for {filepath} — skipping quote check")
            continue

        normalized_quote = normalize(blockquote)
        normalized_page = normalize(page_content)

        if normalized_quote in normalized_page:
            print(f"OK    Quote verified in {filepath}")
        else:
            has_failures = True
            print(f"FAIL  Quote NOT found at source URL for {filepath}")
            print(f"      URL: {source_url}")
            print(f"      Quote: {blockquote[:200]}{'...' if len(blockquote) > 200 else ''}")

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
