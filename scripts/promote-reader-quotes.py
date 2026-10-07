#!/usr/bin/env python3
"""Promote curated comments from the local archive into the published chorus band.

The archive at data/archive/linkedin-comments/ is gitignored and deliberately
permissive — "astounding" and "This is amazing" belong there because they make
good poster cards (Eric, 2026-10-03). The timeline is a higher bar: it is the
public record, not a social asset.

So promotion is explicit. Nothing reaches the site until it is named here.

  promote-reader-quotes.py --list                 # archive candidates not yet published
  promote-reader-quotes.py --add <identifier>...  # promote by identifier
  promote-reader-quotes.py --remove <url>...      # unpublish
  promote-reader-quotes.py --check                # verify the published file

Published file: data/reader-quotes.json (committed).
"""
import argparse, json, glob, re, sys
from pathlib import Path

# LinkedIn headlines are full of decorative emoji ("Launching Innovation 💡🔥🚀").
# They add nothing to a role line and make the band look like a feed.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U00002300-\U000023FF\U0000FE00-\U0000FE0F\U0000200D]"
)


def clean_title(s: str) -> str:
    s = _EMOJI.sub("", s or "")
    return re.sub(r"\s{2,}", " ", s).strip(" ·|-—")

REPO = Path(__file__).resolve().parent.parent
ARCHIVE = REPO / "data/archive/linkedin-comments"
PUBLISHED = REPO / "data/reader-quotes.json"

HEADER = (
    "Curated reader quotes shown in the timeline's chorus band. Promoted from the "
    "gitignored comment archive by scripts/promote-reader-quotes.py. The archive bar "
    "is deliberately low (good poster fodder); this file is the public record and is "
    "held higher. Only ADD deliberately."
)


def load_published() -> dict:
    if PUBLISHED.exists():
        return json.loads(PUBLISHED.read_text())
    return {"_comment": HEADER, "quotes": []}


def save_published(doc: dict) -> None:
    doc["_comment"] = HEADER
    doc["quotes"].sort(key=lambda q: (q.get("date", ""), q.get("author", "")), reverse=True)
    PUBLISHED.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def load_archive() -> list[dict]:
    recs = []
    for f in sorted(glob.glob(str(ARCHIVE / "2026-*.json"))):
        try:
            recs += json.loads(Path(f).read_text())
        except Exception as ex:
            print(f"  ! skipping {f}: {ex}", file=sys.stderr)
    return recs


def to_quote(rec: dict) -> dict:
    a = rec.get("author") or {}
    headline = (a.get("headline") or "").split("|")[0].strip()
    return {
        "quote": (rec.get("pull_quote") or "").strip(),
        "author": a.get("name") or "",
        "title": clean_title(headline)[:60],
        "url": rec.get("permalink") or "",
        "date": (rec.get("posted_at") or rec.get("captured_at") or "")[:10],
        "identifier": rec.get("identifier") or "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--add", nargs="+", metavar="IDENTIFIER")
    g.add_argument("--remove", nargs="+", metavar="URL")
    g.add_argument("--check", action="store_true")
    args = ap.parse_args()

    doc = load_published()
    published_ids = {q.get("identifier") for q in doc["quotes"]}
    published_urls = {q.get("url") for q in doc["quotes"]}

    if args.list:
        recs = load_archive()
        n = 0
        for r in recs:
            q = to_quote(r)
            if not q["quote"] or q["identifier"] in published_ids:
                continue
            n += 1
            print(f'{q["identifier"]}')
            print(f'   {q["date"]}  {q["author"]} — {q["title"][:44]}')
            print(f'   "{q["quote"]}"')
        print(f"\n{n} archive candidates not yet published "
              f"({len(doc['quotes'])} already published).")
        return 0

    if args.check:
        bad = [q for q in doc["quotes"] if not q.get("quote") or not q.get("author") or not q.get("date")]
        dupes = len(doc["quotes"]) - len({q.get("url") for q in doc["quotes"]})
        print(f"{len(doc['quotes'])} published quotes")
        print(f"  incomplete records : {len(bad)}")
        print(f"  duplicate urls     : {dupes}")
        for q in bad:
            print(f"   ! {q}")
        return 1 if (bad or dupes) else 0

    if args.add:
        by_id = {}
        for r in load_archive():
            q = to_quote(r)
            if q["identifier"]:
                by_id[q["identifier"]] = q
        added = 0
        for ident in args.add:
            q = by_id.get(ident)
            if not q:
                print(f"  ! not found in archive: {ident}", file=sys.stderr)
                continue
            if q["identifier"] in published_ids or q["url"] in published_urls:
                print(f"  = already published: {q['author']}")
                continue
            doc["quotes"].append(q)
            published_ids.add(q["identifier"])
            published_urls.add(q["url"])
            added += 1
            print(f'  + {q["author"]}: "{q["quote"][:60]}"')
        save_published(doc)
        print(f"\n{added} added; {len(doc['quotes'])} published total.")
        return 0

    if args.remove:
        before = len(doc["quotes"])
        doc["quotes"] = [q for q in doc["quotes"] if q.get("url") not in set(args.remove)]
        save_published(doc)
        print(f"removed {before - len(doc['quotes'])}; {len(doc['quotes'])} remain.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
