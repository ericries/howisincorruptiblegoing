#!/usr/bin/env python3
"""Verify that each entry's blockquote text appears at its source_url.

Usage:
    python scripts/review_bot/verify_quotes.py content/entries/file1.json ...

Warns (but does not fail) if the URL is unreachable, and says so in a closing
summary. It cannot do better: 62% of entries cite LinkedIn or X, which no
anonymous fetch can read, so failing on unreachable would block every PR.

That means THIS IS NOT THE REAL QUOTE GATE for most entries. The real one is
`scripts/quote_integrity.py`, which checks the blockquote against the source
text the scanner captured at ship time. It runs in the pre-commit hook rather
than here because `data/archive/` is gitignored and so does not exist in CI.

Measured 2026-10-28: this script reported no failures on runs where it had
verified nothing at all, because "could not fetch" printed WARN and continued.
The summary below exists so that outcome can never again read as success.
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


# Below this, a response cannot plausibly be an article, review or post body.
# The Goodreads shell that produced a false FAIL on 2026-10-28 was 13KB of
# markup carrying no review text.
MIN_PLAUSIBLE_CHARS = 1200

# A quote prefix shorter than this matches too much to prove we have the right
# page — "astounding" appears in plenty of unrelated markup.
MIN_PREFIX_SIGNAL = 25


def is_conclusive(*, page: str, quote: str, attribution: str | None) -> bool:
    """Is there positive evidence this response is the document we asked for?

    A quote missing from a page only refutes the entry if we actually received
    the page. A JS shell, cookie wall or captcha returns 200 with no article
    body, and calling that "quote not found" blocks a sound entry — which is
    what happened to a Goodreads review on 2026-10-28.

    Two signals count, either alone: the author's name appears, or enough of
    the quote's opening appears that we are plainly on the right text. Length
    alone is not a signal — walls can be long — but being far too short rules
    a response out.
    """
    if not page or len(page) < MIN_PLAUSIBLE_CHARS:
        return False
    low = page.lower()
    if attribution and attribution.strip() and attribution.strip().lower() in low:
        return True
    prefix = normalize(quote or "")[:40]
    return len(prefix) >= MIN_PREFIX_SIGNAL and prefix in normalize(page)


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> int:
    changed_files = sys.argv[1:]

    if not changed_files:
        print("No entry files specified — nothing to verify.")
        return 0

    has_failures = False
    checked = 0
    unreachable = 0

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
            print(f"WARN  Could not fetch {source_url} for {filepath} — NOT VERIFIED HERE")
            unreachable += 1
            continue

        if not is_conclusive(page=page_content, quote=blockquote,
                             attribution=data.get("attribution")):
            print(f"WARN  {source_url} returned no usable document for {filepath} "
                  f"(JS shell, cookie wall or captcha) — NOT VERIFIED HERE")
            unreachable += 1
            continue

        normalized_quote = normalize(blockquote)
        normalized_page = normalize(page_content)

        checked += 1
        if normalized_quote in normalized_page:
            print(f"OK    Quote verified in {filepath}")
        else:
            has_failures = True
            print(f"FAIL  Quote NOT found at source URL for {filepath}")
            print(f"      URL: {source_url}")
            print(f"      Quote: {blockquote[:200]}{'...' if len(blockquote) > 200 else ''}")

    total = len(changed_files)
    print(f"\nQuote check: verified {checked} of {total} changed entries "
          f"against the live page; {unreachable} unreachable.")
    if checked == 0 and total:
        print("NOTE  Nothing was verified here. Auth-walled sources are covered "
              "offline by scripts/quote_integrity.py in the pre-commit hook, "
              "which cannot run in CI because data/archive/ is gitignored.")

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
