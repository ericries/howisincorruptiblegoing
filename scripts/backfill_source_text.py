"""Recover source text for entries that shipped without it.

    python3 scripts/backfill_source_text.py --plan          # what is recoverable, by route
    python3 scripts/backfill_source_text.py --local         # free: from raw archives already on disk
    python3 scripts/backfill_source_text.py --fetch [--limit N]   # free: plain HTTP, with extraction
    python3 scripts/backfill_source_text.py --from-dataset <id> --platform linkedin

625 entries carry a blockquote and no captured source text, so nothing can
verify them (docs/postmortems/2026-10-28-the-quote-gate-verified-three-percent.md).
`quote_integrity --require-capture` stops that backlog growing. This recovers
what is still recoverable, cheapest route first.

THE RULE THAT MATTERS: a bad capture is worse than none. Saving a JS shell or a
cookie wall would make `quote_integrity` report ABSENT for a sound entry, which
is precisely the false accusation its first run produced. So nothing is written
unless the text is plausibly the document.

"Contains the quote" is deliberately NOT that test. Saving only text that agrees
with the entry would make the checker vacuous — a capture that proves an entry
WRONG is the most valuable kind there is.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "review_bot"))

from quote_integrity import (  # noqa: E402
    ENTRIES,
    SOURCE_TEXTS,
    _url_key,
    missing_capture,
)
from verify_quotes import is_conclusive  # noqa: E402

UA = "Mozilla/5.0 (compatible; IncorruptibleBot/1.0)"

# Hosts no anonymous fetch can read. They need an Apify route, not a retry.
AUTH_WALLED = ("linkedin.com", "x.com", "twitter.com", "instagram.com",
               "tiktok.com", "facebook.com")

# Hosts measured on 2026-10-28 to return a shell, a 403, or a page that simply
# does not carry the quoted text. Listed so --plan can tell the difference
# between "not tried yet" and "tried and known not to work".
KNOWN_UNRECOVERABLE = {
    "incorruptible.co": "homepage renders ~7KB carrying 4 of 55 blurbs; the rest are not published there",
    "amazon.com": "403 to anonymous clients; bestseller pages are generated per-request anyway",
    "forbes.com": "403 to anonymous clients",
    "usatoday.com": "403 to anonymous clients",
    "nytimes.com": "paywalled",
    "wsj.com": "paywalled",
    "ft.com": "paywalled",
}

_TAGS = re.compile(r"(?s)<[^>]+>")
_DROP = re.compile(r"(?is)<(script|style|noscript|template)\b.*?</\1>")


def extract_text(raw: str) -> str:
    """Visible text from an HTML page.

    Run before any matching. Testing a quote against raw markup is why the
    incorruptible.co blurbs looked absent: they are split across tags, so a
    substring search over the HTML finds none of them even when they are there.
    """
    if not raw:
        return ""
    raw = _DROP.sub(" ", raw)
    return re.sub(r"\s+", " ", _html.unescape(_TAGS.sub(" ", raw))).strip()


def should_save(entry: dict, text: str) -> bool:
    """Is this plausibly the document the entry cites?

    Delegates to the same `is_conclusive` the verifiers use, so a page that
    cannot convict an entry also cannot be stored as evidence against it.
    """
    return is_conclusive(page=text, quote=entry.get("blockquote", ""),
                         attribution=entry.get("attribution"))


# Shortest text that can meaningfully be a post. Below this there is nothing
# to verify against either way.
MIN_POST_CHARS = 20


def should_save_known_url(entry: dict, text: str) -> bool:
    """Provenance for a url-keyed dataset, where it is established not inferred.

    `should_save` guesses whether a fetched PAGE is the right document, because
    a fetch can land on a shell, a wall or a redirect. A dataset keyed by post
    url is a different situation: we asked the scraper for that exact url and
    it returned that exact url. Applying the HTML heuristic here would reject
    every post shorter than 1200 characters — which is most LinkedIn posts, and
    would have silently dropped the bulk of a 353-entry backfill.
    """
    return len((text or "").strip()) >= MIN_POST_CHARS


def build_record(entry: dict, text: str, *, platform: str, captured_at: str,
                 backfilled: bool = False) -> dict:
    """The capture record, in the shape quote_integrity reads."""
    rec = {
        "entry_id": entry.get("id", ""),
        "source_url": entry.get("source_url", ""),
        "platform": platform,
        "captured_at": captured_at,
        "chars": len(text),
        "full_text": text,
    }
    if backfilled:
        # Weaker evidence than a ship-time capture: the page may have changed
        # in the months since. Worth knowing when a mismatch turns up later.
        rec["backfilled"] = True
    # How much this capture is allowed to prove. A scraped HTML page may be
    # nothing but nav and headline, so it can confirm a quote but must never
    # convict one. A url-keyed API response is the whole post and may.
    rec["evidence"] = "weak" if platform == "web" else "strong"
    return rec


def save_record(rec: dict, archive_dir: Path = SOURCE_TEXTS) -> Path:
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    p = archive_dir / f"{rec['entry_id']}.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return p


# --- entry loading -------------------------------------------------------------------

def load_entries() -> list[dict]:
    out = []
    for f in sorted(ENTRIES.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return out


def gap_entries() -> list[dict]:
    entries = load_entries()
    gaps = set(missing_capture(entries))
    return [e for e in entries if e.get("id") in gaps]


def _host(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1).lower() if m else ""


def route_for(entry: dict) -> str:
    """Which recovery route this entry needs."""
    url = entry.get("source_url") or ""
    host = _host(url)
    if not url:
        return "no-url"
    for bad, _ in KNOWN_UNRECOVERABLE.items():
        if host == bad or host.endswith("." + bad):
            return "unrecoverable"
    # A bare domain root is not a stable document. The homepage served today is
    # not the one the entry quoted months ago, so a capture of it can only ever
    # manufacture a false ABSENT. Three were stored on the first backfill run
    # before this rule existed.
    if re.sub(r"^https?://[^/]+", "", url) in ("", "/"):
        return "unstable-url"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube-transcript"
    for w in AUTH_WALLED:
        if w in url:
            return "apify:" + w.split(".")[0]
    return "fetch"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- routes ---------------------------------------------------------------------------

def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


URL_FIELDS = ("linkedinUrl", "url", "twitterUrl", "webVideoUrl", "webUrl", "postUrl")
TEXT_FIELDS = ("content", "fullText", "text", "commentary", "full_text", "description")


def index_local_archives(root: Path) -> dict[str, tuple[str, str]]:
    """url-key -> (text, source-file), from every raw dataset already on disk."""
    idx: dict[str, tuple[str, str]] = {}
    for f in root.glob("*/*.json"):
        if f.parent.name == "source-texts":
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for node in _walk(data):
            url = next((node[k] for k in URL_FIELDS
                        if isinstance(node.get(k), str) and node[k].startswith("http")), None)
            if not url:
                continue
            # Goodreads nests the review url one level down.
            text = max((node.get(k) or "" for k in TEXT_FIELDS), key=len)
            if len(text) < 40:
                continue
            key = _url_key(url)
            if key not in idx or len(text) > len(idx[key][0]):
                idx[key] = (text, f.name)
    return idx


def run_local(entries: list[dict], archive_root: Path) -> tuple[int, int]:
    idx = index_local_archives(archive_root)
    saved = skipped = 0
    for e in entries:
        hit = idx.get(_url_key(e.get("source_url")))
        if not hit:
            continue
        text, src = hit
        if not should_save(e, text):
            skipped += 1
            continue
        save_record(build_record(e, text, platform="local-archive",
                                 captured_at=_now(), backfilled=True))
        saved += 1
        print(f"  saved {e['id']}  (from {src})")
    return saved, skipped


def fetch_text(url: str, timeout: int = 20) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return extract_text(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def run_fetch(entries: list[dict], limit: int | None = None) -> tuple[int, int, int]:
    saved = shells = failed = 0
    todo = [e for e in entries if route_for(e) == "fetch"]
    if limit:
        todo = todo[:limit]
    for e in todo:
        text = fetch_text(e["source_url"])
        if text is None:
            failed += 1
            print(f"  unreachable  {e['id']}")
            continue
        if not should_save(e, text):
            shells += 1
            print(f"  not-the-doc  {e['id']}  ({len(text)} chars)")
            continue
        save_record(build_record(e, text, platform="web",
                                 captured_at=_now(), backfilled=True))
        saved += 1
        print(f"  saved        {e['id']}  ({len(text)} chars)")
    return saved, shells, failed


def run_from_dataset(entries: list[dict], dataset_id: str, platform: str) -> tuple[int, int]:
    """Ingest an Apify dataset keyed by post url — the auth-walled route.

    The dataset is fetched here rather than through the Apify MCP tool because
    the items endpoint is a plain GET and the MCP response carries a field-schema
    dump that is 15x larger (see scan-triage.py).
    """
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json&clean=true"
    with urllib.request.urlopen(url, timeout=120) as r:
        data = json.loads(r.read().decode())
    idx: dict[str, str] = {}
    for node in _walk(data):
        u = next((node[k] for k in URL_FIELDS
                  if isinstance(node.get(k), str) and node[k].startswith("http")), None)
        if not u:
            continue
        text = max((node.get(k) or "" for k in TEXT_FIELDS), key=len)
        if len(text) >= 40:
            key = _url_key(u)
            if key not in idx or len(text) > len(idx[key]):
                idx[key] = text
    saved = skipped = 0
    for e in entries:
        text = idx.get(_url_key(e.get("source_url")))
        if not text:
            continue
        if not should_save_known_url(e, text):
            skipped += 1
            continue
        save_record(build_record(e, text, platform=platform,
                                 captured_at=_now(), backfilled=True))
        saved += 1
        print(f"  saved {e['id']}")
    return saved, skipped


# --- CLI --------------------------------------------------------------------------------

def _plan(entries: list[dict]) -> None:
    import collections
    routes = collections.Counter(route_for(e) for e in entries)
    print(f"{len(entries)} entries need a capture.\n")
    for route, n in routes.most_common():
        print(f"  {n:4}  {route}")
    print("\nKnown-unrecoverable hosts and why:")
    for h, why in KNOWN_UNRECOVERABLE.items():
        n = sum(1 for e in entries if _host(e.get('source_url') or '') == h)
        if n:
            print(f"  {n:4}  {h:24} {why}")


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--from-dataset")
    ap.add_argument("--platform", default="linkedin")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    entries = gap_entries()

    if args.plan or not (args.local or args.fetch or args.from_dataset):
        _plan(entries)
        return 0
    if args.local:
        saved, skipped = run_local(entries, SOURCE_TEXTS.parent)
        print(f"\nlocal: saved {saved}, rejected {skipped} as not-the-document")
    if args.fetch:
        saved, shells, failed = run_fetch(entries, args.limit)
        print(f"\nfetch: saved {saved}, rejected {shells} shells, {failed} unreachable")
    if args.from_dataset:
        saved, skipped = run_from_dataset(entries, args.from_dataset, args.platform)
        print(f"\ndataset: saved {saved}, rejected {skipped} as not-the-document")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
