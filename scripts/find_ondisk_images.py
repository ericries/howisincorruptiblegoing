#!/usr/bin/env python3
"""Report unimaged entries whose headshot is already in public/images/people/.

    python3 scripts/find_ondisk_images.py           # report
    python3 scripts/find_ondisk_images.py --wire    # attach the unambiguous ones

On 2026-10-23 Bob Sutton's photo was found on disk as robert-sutton.jpg, having
never been wired to his entry. The scan prompts gained a line saying "check the
disk first". The next morning that line found five more — which is the point: an
instruction that pays off five times in one day is describing a job a script
should be doing. Checking by hand also costs a judgment call every time, and the
first hand-rolled attempt got it wrong (see below).

MATCHING IS DELIBERATELY STRICT. The first pass used substring matching and
returned 41 "hits", including "Ann Armbrecht" against susanne-h(ann)estad.jpg.
No image beats a wrong face, so a match needs the entry's whole name to equal
the file's whole stem. Single-token names never match at all.

`vouched_by` is the identity evidence: another entry already using that file for
that same person means the photo was checked when it was first downloaded. An
unvouched match is still reported, but it is a first use and deserves a look.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content" / "entries"
PEOPLE = ROOT / "public" / "images" / "people"
# Tracked, NOT under data/archive/ which is gitignored. Everything the
# scanner needs lives in this repository so it survives a change of machine.
SKIPS = ROOT / "data" / "ondisk-image-skips.json"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def slugify(name: str) -> str:
    """'Sara Muñoz Madrid' -> 'sara-munoz-madrid'. Accents folded so the ASCII
    filenames on disk can match the name as it is written in the entry."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def _names(attribution: str) -> list[str]:
    """Split a multi-person attribution. 'Yvonne Bajela & Maria Rotilu' is two
    people sharing one entry, and either may be the one we have a photo of."""
    parts = [p.strip() for p in re.split(r"\s*(?:&|,| and )\s*", attribution)]
    return [p for p in parts if p]


def find_matches(entries: list[dict], filenames: set[str],
                 skips: dict[str, str] | None = None) -> list[dict]:
    """Unimaged entries whose attribution exactly matches a file stem.

    `skips` maps entry id -> reason, for matches that were looked at and
    rejected. Without it a rejected match reports on every run; scan-coverage
    established in October that a signal nobody can clear becomes a signal
    nobody reads.
    """
    skips = skips or {}
    by_stem: dict[str, str] = {}
    for f in sorted(filenames):
        stem, dot, ext = f.rpartition(".")
        if dot and f".{ext.lower()}" not in IMAGE_EXTS:
            continue
        by_stem.setdefault(slugify(stem or f), f)

    # Which entries already use each file, and for whom — the identity evidence.
    vouchers: dict[str, list[str]] = {}
    for e in entries:
        ai = e.get("attribution_image")
        if ai:
            vouchers.setdefault(ai.rsplit("/", 1)[-1], []).append(e.get("id", ""))

    out: list[dict] = []
    for e in entries:
        if e.get("image") or e.get("attribution_image"):
            continue
        if e.get("id") in skips:
            continue
        attribution = e.get("attribution")
        if not attribution:
            continue
        people = _names(attribution)
        for person in people:
            slug = slugify(person)
            # A single token is never specific enough to identify a person.
            if slug.count("-") < 1:
                continue
            f = by_stem.get(slug)
            if not f:
                continue
            out.append({
                "id": e.get("id", ""),
                "attribution": attribution,
                "matched_name": person,
                "file": f,
                "path": f"/images/people/{f}",
                "ambiguous": len(people) > 1,
                "vouched_by": sorted(v for v in vouchers.get(f, []) if v),
            })
            break
    return out


def _load_entries() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(ENTRIES.glob("*.json"))]


def _load_skips() -> dict[str, str]:
    return json.loads(SKIPS.read_text()) if SKIPS.exists() else {}


def _wire(match: dict) -> None:
    p = ENTRIES / f"{match['id']}.json"
    e = json.loads(p.read_text(), object_pairs_hook=OrderedDict)
    e["attribution_image"] = match["path"]
    p.write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n")


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wire", action="store_true",
                    help="attach unambiguous matches (skips multi-person entries)")
    args = ap.parse_args(argv)

    entries = _load_entries()
    filenames = {f.name for f in PEOPLE.iterdir() if f.is_file()} if PEOPLE.is_dir() else set()
    matches = find_matches(entries, filenames, skips=_load_skips())

    if not matches:
        print("No unimaged entry has a headshot already on disk.")
        return 0

    print(f"{len(matches)} unimaged entry(ies) already have a photo on disk:\n")
    wired = 0
    for m in matches:
        flags = []
        if m["ambiguous"]:
            flags.append("AMBIGUOUS: multi-person attribution, decide by hand")
        if not m["vouched_by"]:
            flags.append("first use of this file — confirm it is the right person")
        else:
            flags.append("vouched by " + ", ".join(m["vouched_by"]))
        print(f"  {m['attribution']:30} -> {m['file']}")
        print(f"     {m['id']}")
        for fl in flags:
            print(f"     · {fl}")
        if args.wire and not m["ambiguous"]:
            _wire(m)
            wired += 1
        print()

    if args.wire:
        print(f"Wired {wired}. Run `npm run build && python3 scripts/check-images-render.py` "
              f"— not every entry type renders attribution_image.")
    else:
        print("Re-run with --wire to attach the unambiguous ones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
