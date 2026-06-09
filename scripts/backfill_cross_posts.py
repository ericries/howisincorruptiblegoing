"""Backfill source markers into data/cross-posts.json from content/entries/*.json.

Usage:
  uv run --with pytest python scripts/backfill_cross_posts.py \\
    --entries-dir content/entries \\
    --state-file data/cross-posts.json

Idempotent: safe to re-run. Existing scheduled timestamps are preserved.
"""
import argparse
import json
import sys
from pathlib import Path

from lib.cross_posts import infer_source_markers, merge_state


def run_backfill(entries_dir: str, state_file: str) -> None:
    entries_path = Path(entries_dir)
    state_path = Path(state_file)

    new_markers: dict = {}
    for entry_file in sorted(entries_path.glob("*.json")):
        entry = json.loads(entry_file.read_text())
        markers = infer_source_markers(entry)
        if markers:
            new_markers[entry["id"]] = markers

    if state_path.exists():
        existing = json.loads(state_path.read_text())
    else:
        existing = {}

    merged = merge_state(existing, new_markers)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(merged, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entries-dir", default="content/entries")
    ap.add_argument("--state-file", default="data/cross-posts.json")
    args = ap.parse_args(argv)
    run_backfill(args.entries_dir, args.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
