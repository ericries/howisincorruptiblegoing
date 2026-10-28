#!/usr/bin/env python3
"""Fetch an Apify dataset, archive it, and print a compact triage table.

Replaces the expensive MCP round-trips in a scan cycle. Measured on the
2026-10-04 session transcript, the three Apify MCP tools accounted for 5.34M of
7.73M tokens of total tool traffic:

    mcp__apify__get-dataset-items   835 calls   2.33M tokens
    mcp__apify__call-actor        1,201 calls   2.31M tokens  (waitSecs>0)
    mcp__apify__get-actor-run       365 calls   0.70M tokens

Most of that is the actor's field-schema dump, repeated in every response and
never used. The cheap path is: ONE `call-actor` with `waitSecs: 0` (609 chars
average vs 9,630 — 15.8x cheaper), then this script to poll, archive and
summarise in a single Bash call.

Usage:
  scan-triage.py <datasetId> --platform linkedin --archive data/archive/linkedin-raw/2026-10-04-kw.json
  scan-triage.py <datasetId> --platform twitter --since 2026-10-03
  scan-triage.py --file data/archive/linkedin-raw/2026-10-04-kw.json --platform linkedin --full 3

Flags:
  --full N      print item N verbatim and entirely (no truncation). Use this
                whenever a ship/skip decision turns on what a post actually
                says — a truncated slice is how the 2026-10-04 Paige Kaye
                entry got wrongly dismissed as a word collision.
  --new-only    hide items whose source_url is already on the timeline.
"""
import argparse, json, re, sys, time, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRIES = REPO / "content/entries"
API = "https://api.apify.com/v2/datasets/{}/items?format=json&clean=true"
META = "https://api.apify.com/v2/datasets/{}"


# ---------- url / dedupe helpers ----------

# Query params that carry no identity — safe to drop before comparing. Anything
# NOT listed here is kept: ?v= is the identity of a YouTube URL, and dropping the
# whole query string collapsed every watch URL to "youtube.com/watch", which
# reported every video as already SHIPPED (caught 2026-10-04 on real scan data).
TRACKING_PARAMS = {
    "si", "t", "feature", "ref", "ref_src", "source", "fbclid", "igshid", "utm",
    "gclid", "mc_cid", "mc_eid", "spm", "rdt", "trk", "trkinfo", "originaltrk",
}


def norm_url(u: str | None) -> str:
    """Scheme/www/fragment-insensitive URL key, preserving identifying query params."""
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u.strip())
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0]
    path, _, query = u.partition("?")
    path = path.rstrip("/").lower()
    if not query:
        return path
    kept = []
    for part in query.split("&"):
        if not part:
            continue
        k, _, v = part.partition("=")
        if k.lower() in TRACKING_PARAMS or k.lower().startswith("utm_"):
            continue
        kept.append(f"{k.lower()}={v}")
    kept.sort()
    return f"{path}?{'&'.join(kept)}" if kept else path


def is_shipped(url: str, shipped: set[str]) -> bool:
    return norm_url(url) in shipped


def author_already_shipped(name: str, known: dict[str, list[str]]) -> list[str]:
    """Entries already on the timeline for this author (2026-10-04 Brian Behm
    duplicate: the check used to happen at `git add` time, far too late)."""
    return known.get((name or "").strip().lower(), [])


def load_shipped() -> tuple[set[str], dict[str, list[str]]]:
    urls: set[str] = set()
    authors: dict[str, list[str]] = {}
    if not ENTRIES.is_dir():
        return urls, authors
    for p in ENTRIES.glob("*.json"):
        try:
            e = json.loads(p.read_text())
        except Exception:
            continue
        for u in [e.get("source_url")] + [
            s.get("url") for s in (e.get("source_urls") or []) if isinstance(s, dict)
        ]:
            if u:
                urls.add(norm_url(u))
        a = (e.get("attribution") or "").strip().lower()
        if a:
            authors.setdefault(a, []).append(e.get("id", p.stem))
    return urls, authors


# ---------- normalisation ----------

def _date(v) -> str:
    if isinstance(v, dict):
        v = v.get("date") or ""
    v = str(v or "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", v)
    if m:
        return m.group(1)
    # Twitter's "Sat Oct 04 13:31:00 +0000 2026"
    m = re.match(r"\w{3} (\w{3}) (\d{2}) [\d:]+ [+\-]\d{4} (\d{4})", v)
    if m:
        mon = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].index(m.group(1)) + 1
        return f"{m.group(3)}-{mon:02d}-{m.group(2)}"
    return v[:10]


def normalise(item: dict, platform: str) -> dict:
    a = item.get("author") or {}
    if platform == "linkedin":
        eng = item.get("engagement") or {}
        return {
            "platform": "linkedin",
            "author": a.get("name") or "",
            "headline": a.get("info") or "",
            "url": item.get("linkedinUrl") or "",
            "date": _date(item.get("postedAt")),
            "likes": eng.get("likes") or 0,
            "comments": eng.get("comments") or 0,
            "text": item.get("content") or "",
            "avatar": ((a.get("avatar") or {}) if isinstance(a.get("avatar"), dict) else {}).get("url"),
        }
    if platform == "twitter":
        return {
            "platform": "twitter",
            "author": "@" + (a.get("userName") or ""),
            "headline": (a.get("description") or "")[:80],
            "followers": a.get("followers") or 0,
            "url": item.get("url") or item.get("twitterUrl") or "",
            "date": _date(item.get("createdAt")),
            "likes": item.get("likeCount") or 0,
            "views": item.get("viewCount") or 0,
            "is_reply": bool(item.get("isReply")),
            "text": item.get("fullText") or item.get("text") or "",
            "avatar": a.get("profilePicture"),
        }
    if platform == "tiktok":
        vm = item.get("videoMeta") or {}
        return {
            "platform": "tiktok",
            "id": str(item.get("id") or ""),
            "author": (item.get("authorMeta") or {}).get("name") or "",
            "url": item.get("webVideoUrl") or "",
            "date": _date(item.get("createTimeISO")),
            "slideshow": bool(item.get("isSlideshow")),
            "duration": vm.get("duration"),
            "plays": item.get("playCount") or 0,
            "likes": item.get("diggCount") or 0,
            "text": item.get("text") or "",
        }
    if platform == "youtube":
        return {
            "platform": "youtube",
            "author": item.get("channelName") or "",
            "subscribers": item.get("numberOfSubscribers") or 0,
            "url": item.get("url") or "",
            "date": _date(item.get("date")),
            "views": item.get("viewCount") or 0,
            "duration": item.get("duration") or "",
            "likes": item.get("likes") or 0,
            "text": item.get("title") or "",
            "title": item.get("title") or "",
        }
    return {"platform": platform, "author": "", "url": "", "date": "",
            "likes": 0, "text": json.dumps(item)[:500]}


# ---------- rendering ----------

def render_row(rec: dict, width: int = 150) -> str:
    """One-line preview that always includes the book mention if there is one.

    A plain head-truncation hides the citation whenever the author opens with a
    generic hook — which is common, and which is how Fora Fereydouni (47
    reactions) was skipped from a 13-item list and Paige Kaye was nearly lost.
    When the mention falls past the cut, the row shows the opening plus the
    sentence that carries it, so the decision is never taken blind.
    """
    body = re.sub(r"\s+", " ", rec.get("text") or "").strip()
    if len(body) <= width:
        return body
    if not citation_below_fold(body, width):
        return body[:width] + "…"

    head = body[: width // 2].rstrip()
    m = _CITATION.search(body, width)

    # Prefer the sentence carrying the mention, but clamp to a window CENTRED on
    # the match: a long unpunctuated post has no sentence bounds to fall back on,
    # and clipping from the sentence start would cut the citation back out.
    sent_start = body.rfind(". ", 0, m.start())
    sent_start = 0 if sent_start == -1 else sent_start + 2
    sent_end = body.find(". ", m.end())
    sent_end = len(body) if sent_end == -1 else sent_end + 1

    lead = 40  # context before the mention
    start = max(sent_start, width // 2, m.start() - lead)
    end = min(sent_end, start + width)
    if end <= m.end():  # never clip the mention itself out of view
        end = min(len(body), m.end() + 20)

    tail = body[start:end].strip()
    if end < sent_end:
        tail += "…"
    return f"{head}… […] {tail}"


# The book reference is frequently buried: people open with a generic hook and
# credit Incorruptible several paragraphs down. Judging from the truncated row
# therefore dismisses real candidates — it nearly lost Paige Kaye and did lose
# five days on Fora Fereydouni (47 reactions, inside a 13-item list). Flagging
# it turns "remember to read the whole post" into something mechanical.
_CITATION = re.compile(r"incorruptible|eric\s+ries", re.I)


def citation_below_fold(text: str, width: int = 150) -> bool:
    """True when the only book/author mention falls past the row's truncation.

    Measured against the same whitespace-collapsed string render_row() prints,
    so the offsets cannot drift apart.
    """
    body = re.sub(r"\s+", " ", text or "").strip()
    if len(body) <= width:
        return False  # nothing is hidden; the row shows the whole post
    visible, hidden = body[:width], body[width:]
    return bool(_CITATION.search(hidden)) and not _CITATION.search(visible)


def render_full(rec: dict) -> str:
    """Entire post, never truncated."""
    out = [
        f"author     : {rec.get('author')}",
        f"headline   : {rec.get('headline','')}",
        f"url        : {rec.get('url')}",
        f"date       : {rec.get('date')}   likes={rec.get('likes')}",
    ]
    for k in ("followers", "subscribers", "views", "plays", "duration", "slideshow", "is_reply"):
        if rec.get(k) is not None and k in rec:
            out.append(f"{k:11}: {rec[k]}")
    if rec.get("avatar"):
        out.append(f"avatar     : {rec['avatar']}")
    out.append("-" * 60)
    out.append(rec.get("text") or "")
    return "\n".join(out)


# ---------- fetch ----------

def _read_items(dataset_id: str) -> list:
    with urllib.request.urlopen(API.format(dataset_id), timeout=60) as r:
        return json.loads(r.read().decode())


def dataset_meta(dataset_id: str) -> dict:
    """The dataset's own record of how much it holds.

    `itemCount` is the only authority on whether a read is complete. It is one
    request away and was never asked for, which is how a 246-item dataset got
    archived as 60 items on 2026-10-28.
    """
    with urllib.request.urlopen(META.format(dataset_id), timeout=60) as r:
        return json.loads(r.read().decode()).get("data", {})


def is_complete(*, n_read: int, item_count: int | None) -> bool:
    """Did this read get everything the dataset says it holds?

    Unknown (`None`) counts as complete: a metadata failure must not block a
    scan. `n_read > item_count` is also complete — the items endpoint can run
    ahead of the counter while a run is writing, and treating that as a failure
    would reject good reads.
    """
    return item_count is None or n_read >= item_count


def fetch(dataset_id: str, expect: int = 0, tries: int = 20, delay: int = 10) -> list:
    """Poll until the read matches the dataset's itemCount, then return it.

    The old stopping condition was `len(items) >= expect` with expect defaulting
    to 1, which meant "return the moment anything exists". Against a run that
    takes 65 seconds to write 246 items, the first poll lands on a partial
    dataset and the script reports success. `expect` is kept as a floor for
    callers who know they need at least N, but it is no longer what decides
    completeness.
    """
    last: list = []
    for i in range(tries):
        try:
            last = _read_items(dataset_id)
        except Exception as ex:
            print(f"  poll {i+1}: {ex}", file=sys.stderr)
            last = []

        try:
            count = dataset_meta(dataset_id).get("itemCount")
        except Exception:
            count = None            # metadata is advisory; never block on it

        # itemCount is read AFTER the items, deliberately. A run writing
        # concurrently can add rows between the two calls; taking the count
        # second means any such growth shows up as count > n_read and costs
        # another poll, rather than being missed. The reverse order can call a
        # read complete that was already stale when it landed.
        if is_complete(n_read=len(last), item_count=count) and len(last) >= expect:
            return last
        if i < tries - 1:
            time.sleep(delay)

    if not is_complete(n_read=len(last), item_count=count):
        print(f"  WARNING: read {len(last)} of {count} items after {tries} polls",
              file=sys.stderr)
    return last


def archive(path, items: list, item_count: int | None = None) -> bool:
    """Write the raw dataset, refusing to replace a fuller file with a thinner one.

    The archive file is the record every later judgement reads — including
    `feed_coverage`, whose job is spotting missing days. Overwriting 246 archived
    items with a partial 60 destroys the evidence and leaves nothing that looks
    wrong. Returns whether it wrote.
    """
    path = Path(path)
    partial = not is_complete(n_read=len(items), item_count=item_count)
    if partial:
        print(f"  WARNING: partial read ({len(items)} of {item_count} items)",
              file=sys.stderr)
        if path.exists():
            try:
                existing = len(json.loads(path.read_text()))
            except (json.JSONDecodeError, OSError):
                existing = 0
            if existing > len(items):
                print(f"  REFUSED: {path} already holds {existing} items; "
                      f"not overwriting with a partial read", file=sys.stderr)
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset_id", nargs="?")
    ap.add_argument("--file", help="read a previously archived JSON instead of fetching")
    ap.add_argument("--platform", required=True,
                    choices=["linkedin", "twitter", "tiktok", "youtube", "generic"])
    ap.add_argument("--archive", help="write the raw dataset here before summarising")
    ap.add_argument("--expect", type=int, default=1, help="poll until at least N items")
    ap.add_argument("--since", help="only show items dated >= this YYYY-MM-DD")
    ap.add_argument("--full", type=int, help="print item N in full, then exit")
    ap.add_argument("--new-only", action="store_true", help="hide already-shipped source_urls")
    ap.add_argument("--width", type=int, default=150)
    args = ap.parse_args()

    if args.file:
        items = json.loads(Path(args.file).read_text())
    elif args.dataset_id:
        items = fetch(args.dataset_id, expect=args.expect)
        if args.archive:
            try:
                count = dataset_meta(args.dataset_id).get("itemCount")
            except Exception:
                count = None
            if archive(args.archive, items, item_count=count):
                print(f"archived {len(items)} items -> {args.archive}")
    else:
        ap.error("need a dataset_id or --file")

    recs = [normalise(it, args.platform) for it in items]
    shipped_urls, known_authors = load_shipped()

    if args.full is not None:
        if not 0 <= args.full < len(recs):
            print(f"index out of range (0..{len(recs)-1})", file=sys.stderr)
            return 2
        print(render_full(recs[args.full]))
        return 0

    shown = 0
    for i, r in enumerate(recs):
        if args.since and r.get("date") and r["date"] < args.since:
            continue
        dup = is_shipped(r.get("url", ""), shipped_urls)
        if dup and args.new_only:
            continue
        prior = author_already_shipped(r.get("author", ""), known_authors)
        marks = []
        if dup:
            marks.append("SHIPPED")
        if prior:
            marks.append(f"AUTHOR-HAS-{len(prior)}")
        if r["platform"] == "tiktok" and r.get("slideshow"):
            marks.append("SLIDESHOW")
        extra = ""
        if r["platform"] == "twitter":
            extra = f" {r.get('followers',0)}f vw{r.get('views',0)}" + (" REPLY" if r.get("is_reply") else "")
        elif r["platform"] == "youtube":
            extra = f" {r.get('subscribers',0)}subs vw{r.get('views',0)} {r.get('duration','')}"
        elif r["platform"] == "tiktok":
            extra = f" plays{r.get('plays',0)} dur={r.get('duration')}"
        flag = ("  [" + ",".join(marks) + "]") if marks else ""
        print(f"[{i}] {r.get('date','')} {r.get('author','')} | "
              f"{(r.get('headline') or '')[:40]} | ♥{r.get('likes',0)}{extra}{flag}")
        print(f"    {render_row(r, args.width)}")
        if prior:
            print(f"    ↳ already on timeline: {', '.join(prior[:3])}")
        shown += 1
    print(f"\n{shown} shown / {len(recs)} total"
          f"{' (since ' + args.since + ')' if args.since else ''}")
    print("Use --full <N> to print any item in its entirety before deciding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
