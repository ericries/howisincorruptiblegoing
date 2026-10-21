#!/usr/bin/env python3
"""Report entry images that never reach the built HTML.

    npm run build && python3 scripts/check-images-render.py

On 2026-10-20 it emerged that 58 `type=reaction` entries carried a sourced
headshot in `attribution_image` which appeared nowhere in the site: the reaction
list rendered author, title, quote and source link, and silently dropped the
image. Every morning scan that had sourced a face for a reaction had been doing
work nobody could see, for weeks.

The entry JSON said the image was there. Lint said the file existed on disk. Both
were true and both were beside the point. The only place the question can be
answered is the build output, so that is what this reads.

This is the mechanism that replaces the prompt line "after attaching an image,
grep dist/ to confirm it renders" — an instruction that was in the prompt and
still had to be remembered.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content" / "entries"
DIST = ROOT / "dist"

IMAGE_FIELDS = ("image", "attribution_image")


def find_orphans(entries: list[dict], html: str) -> list[dict]:
    """Image paths referenced by entries but absent from the rendered HTML."""
    out: list[dict] = []
    for e in entries:
        for field in IMAGE_FIELDS:
            path = (e.get(field) or "").strip()
            if not path:
                continue
            # A query string or fragment on the rendered src must still count as
            # a hit, so compare on the path alone.
            if path not in html:
                out.append({"entry": e.get("id", "?"), "type": e.get("type", "?"),
                            "field": field, "path": path})
    return out


def summarise(orphans: list[dict]) -> str:
    """One line per (type, field) bucket.

    The signature of a component that forgot a field is every entry of one type
    missing the same field at once — 58 identical lines would bury that, so the
    buckets lead and examples follow.
    """
    if not orphans:
        return "All entry images appear in the build."
    buckets = Counter((o["type"], o["field"]) for o in orphans)
    lines = [f"{len(orphans)} image reference(s) missing from the build:"]
    for (etype, field), n in buckets.most_common():
        lines.append(f"  {n:4d}  type={etype:11s} field={field}")
        examples = [o for o in orphans if o["type"] == etype and o["field"] == field][:3]
        for ex in examples:
            lines.append(f"        {ex['entry']}  {ex['path']}")
        if n > len(examples):
            lines.append(f"        … and {n - len(examples)} more")
    if any(n >= 5 for n in buckets.values()):
        lines.append("")
        lines.append("A whole bucket missing at once usually means the component for that")
        lines.append("type never renders the field — check the .astro, not the entries.")
    return "\n".join(lines)


def _load_entries() -> list[dict]:
    out = []
    for f in sorted(ENTRIES.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except ValueError:
            continue
    return out


def _load_html() -> str:
    if not DIST.is_dir():
        print("dist/ not found — run `npm run build` first.", file=sys.stderr)
        raise SystemExit(2)
    return "\n".join(p.read_text(errors="ignore") for p in DIST.rglob("*.html"))


def _main(argv: list[str]) -> int:
    orphans = find_orphans(_load_entries(), _load_html())
    print(summarise(orphans))
    # Advisory by default: a genuinely unreferenced image is sometimes correct
    # (an entry below the index fold with no detail page). --strict for CI.
    return 1 if (orphans and "--strict" in argv) else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
