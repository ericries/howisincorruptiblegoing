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
    body = re.sub(r"\s+", " ", rec.get("text") or "").strip()
    if len(body) > width:
        body = body[:width] + "…"
    return body


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

def fetch(dataset_id: str, expect: int = 1, tries: int = 20, delay: int = 10) -> list:
    url = API.format(dataset_id)
    last: list = []
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                last = json.loads(r.read().decode())
        except Exception as ex:
            print(f"  poll {i+1}: {ex}", file=sys.stderr)
            last = []
        if len(last) >= expect:
            return last
        time.sleep(delay)
    return last


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
            p = Path(args.archive)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(items, ensure_ascii=False, indent=1))
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
