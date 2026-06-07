#!/usr/bin/env python3
"""Backfill quote-card images for entries that lack a native image.

Usage:
  python3 scripts/backfill-quote-cards.py                  # all eligible entries
  python3 scripts/backfill-quote-cards.py <entry-id>...    # specific entry IDs

Eligible = type in {endorsement, review, media} AND no existing image AND a
non-empty blockquote AND not an Eric Ries / @ericriesactual self-post.

Renders /public/images/cards/<id>.png for each eligible entry and sets
entry.image = "/images/cards/<id>.png". Idempotent — entries that already
have an image (even a card) are skipped.

Designed to run at the end of every daily scan so newly-shipped entries
get a card automatically without each cron prompt re-implementing the loop.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content/entries"
CARDS = ROOT / "public/images/cards"
GENERATOR = ROOT / "scripts/generate-quote-card.py"

ELIGIBLE_TYPES = {"endorsement", "review", "media"}

def is_eligible(d: dict) -> bool:
    if d.get("image"):
        return False
    if d.get("type") not in ELIGIBLE_TYPES:
        return False
    if not (d.get("blockquote") or "").strip():
        return False
    src = (d.get("blockquote_source") or "").strip()
    if src.startswith("Eric Ries") or src.startswith("@ericriesactual"):
        return False
    return True

def main() -> int:
    target_ids = set(sys.argv[1:])
    files = sorted(ENTRIES.glob("*.json"))
    generated, skipped = [], 0
    for f in files:
        d = json.loads(f.read_text())
        if target_ids and d["id"] not in target_ids:
            continue
        if not is_eligible(d):
            skipped += 1
            continue
        out = CARDS / f"{d['id']}.png"
        subprocess.run(
            ["python3", str(GENERATOR), str(f), str(out)],
            check=True, capture_output=True,
        )
        d["image"] = f"/images/cards/{d['id']}.png"
        f.write_text(json.dumps(d, indent=2) + "\n")
        generated.append(d["id"])
        print(f"  ✓ {d['id']}")
    print(f"\nGenerated {len(generated)} card(s); skipped {skipped} (already-imaged / ineligible).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
