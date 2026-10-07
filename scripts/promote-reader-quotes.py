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


def avatar_slug(name: str) -> str:
    s = _EMOJI.sub("", name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "reader"


def is_real_avatar(url: str | None) -> bool:
    """LinkedIn serves a generic silhouette from static.licdn.com when a user
    has no photo. Saving those would line the band with identical grey heads."""
    if not url:
        return False
    return "media.licdn.com" in url


REPO = Path(__file__).resolve().parent.parent
ARCHIVE = REPO / "data/archive/linkedin-comments"
PUBLISHED = REPO / "data/reader-quotes.json"
AVATARS = REPO / "public/images/readers"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

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
        "profile_url": a.get("profile_url") or "",
    }


def fetch_avatar(q: dict) -> str | None:
    """Pull the reader's photo from their public LinkedIn profile and save a
    small square to public/images/readers/. Returns the site-relative path, or
    None when there is no real photo — the band renders fine without one."""
    import subprocess
    profile = (q.get("profile_url") or "").split("?")[0]
    if not profile:
        return None
    slug = avatar_slug(q["author"])
    dest = AVATARS / f"{slug}.jpg"
    rel = f"/images/readers/{slug}.jpg"
    if dest.exists():
        return rel

    try:
        html = subprocess.run(["curl", "-sSL", "-A", UA, "--max-time", "20", profile],
                              capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    m = re.search(r'og:image"\s+content="([^"]+)"', html)
    if not m:
        return None
    url = m.group(1).replace("&amp;", "&")
    if not is_real_avatar(url):
        return None

    AVATARS.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["curl", "-sSL", "--max-time", "25", "-o", str(dest), url],
                       capture_output=True, timeout=40)
        from PIL import Image
        im = Image.open(dest)          # raises if the download is not an image
        side = min(im.size)
        left = (im.width - side) // 2
        # Bias the vertical crop upward. A centre crop of a full-length photo
        # lands on the torso and the face disappears at 28px (observed on Mary
        # Bonsor's profile, 2026-10-07).
        top = int((im.height - side) * 0.22)
        im.convert("RGB").crop((left, top, left + side, top + side)) \
          .resize((128, 128), Image.LANCZOS).save(dest, quality=88)
    except Exception:
        dest.unlink(missing_ok=True)
        return None
    return rel


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--add", nargs="+", metavar="IDENTIFIER")
    g.add_argument("--remove", nargs="+", metavar="URL")
    g.add_argument("--check", action="store_true")
    g.add_argument("--faces", action="store_true",
                   help="fetch missing reader photos for already-published quotes")
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
            face = fetch_avatar(q)
            if face:
                q["avatar"] = face
            q.pop("profile_url", None)
            doc["quotes"].append(q)
            published_ids.add(q["identifier"])
            published_urls.add(q["url"])
            added += 1
            print(f'  + {q["author"]}: "{q["quote"][:60]}"')
        save_published(doc)
        print(f"\n{added} added; {len(doc['quotes'])} published total.")
        return 0

    if args.faces:
        by_id = {}
        for r in load_archive():
            qq = to_quote(r)
            if qq["identifier"]:
                by_id[qq["identifier"]] = qq
        got = 0
        for q in doc["quotes"]:
            if q.get("avatar"):
                continue
            src = by_id.get(q.get("identifier"))
            if not src:
                print(f"  ? no archive record for {q['author']}")
                continue
            face = fetch_avatar({**q, "profile_url": src.get("profile_url", "")})
            if face:
                q["avatar"] = face
                got += 1
                print(f"  + {q['author']} -> {face}")
            else:
                print(f"  - no photo for {q['author']}")
        save_published(doc)
        have = sum(1 for q in doc["quotes"] if q.get("avatar"))
        print(f"\n{got} fetched; {have}/{len(doc['quotes'])} published quotes now have a face.")
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
