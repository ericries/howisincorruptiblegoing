#!/usr/bin/env python3
"""Generate share-ready quote cards for the day's best archived LinkedIn comments.

Reads data/archive/linkedin-comments/YYYY-MM-DD.json (or today's file by default),
sorts records by likes desc then confidence, and renders up to N cards to
data/social-cards/YYYY-MM-DD/<slug>.png using the same visual style as the
timeline entry quote cards.

Usage:
  python3 scripts/generate-comment-cards.py                  # today's archive, top 6
  python3 scripts/generate-comment-cards.py 2026-09-15       # specific date
  python3 scripts/generate-comment-cards.py 2026-09-15 10    # top 10 instead of 6
  python3 scripts/generate-comment-cards.py --all            # all records today
"""
import json, re, sys, tempfile
from datetime import date
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts/generate-quote-card.py"
ARCHIVE_DIR = ROOT / "data/archive/linkedin-comments"
OUT_DIR = ROOT / "data/social-cards"


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:maxlen] or "anon"


def _substantive_text(r: dict) -> str:
    """Best text to use as the quote — pull_quote if the archive computed one,
    otherwise full_text/text trimmed."""
    q = (r.get("pull_quote") or "").strip()
    if q and len(q) > 20:
        return q
    text = (r.get("full_text") or r.get("text") or "").strip()
    return text


def _rank_key(r: dict):
    """Sort key: high likes first, high-confidence first."""
    likes = int(r.get("likes") or 0)
    low = 1 if r.get("low_confidence") else 0
    return (-likes, low)


def render_card(record: dict, date_str: str, out_dir: Path) -> Path:
    """Render one card by shaping the archive record into the entry schema
    the existing generate-quote-card.py expects, then invoking it."""
    author = record.get("author") or {}
    name = author.get("name") or "Anonymous"
    headline = author.get("headline") or ""
    url = record.get("permalink") or record.get("url") or ""
    quote = _substantive_text(record)

    # Shape into the same schema as a content entry
    entry_id = f"{date_str}-{_slug(name)}"
    shim = {
        "id": entry_id,
        "blockquote": quote,
        "attribution": name,
        "attribution_title": headline,
        "source_url": url,
    }

    # Write a temp entry JSON for the renderer
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(shim, tf)
        tf.flush()
        tmp_path = Path(tf.name)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{entry_id}.png"
    try:
        subprocess.run(
            ["python3", str(GENERATOR), str(tmp_path), str(out_path)],
            check=True, capture_output=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return out_path


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    date_str = args[0] if args and re.match(r"\d{4}-\d{2}-\d{2}", args[0]) else date.today().isoformat()
    top_n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 6
    if "--all" in flags:
        top_n = 10_000

    archive_file = ARCHIVE_DIR / f"{date_str}.json"
    if not archive_file.exists():
        print(f"No archive file for {date_str} at {archive_file}")
        return 1

    records = json.loads(archive_file.read_text())
    records = [r for r in records if _substantive_text(r)]
    records.sort(key=_rank_key)
    records = records[:top_n]

    out_dir = OUT_DIR / date_str
    print(f"Rendering {len(records)} card(s) for {date_str} → {out_dir.relative_to(ROOT)}/")
    for r in records:
        p = render_card(r, date_str, out_dir)
        author = (r.get("author") or {}).get("name", "?")
        likes = r.get("likes", 0) or 0
        low = " [LOW]" if r.get("low_confidence") else ""
        print(f"  ✓ {author:40}  likes={likes:<4}{low}  → {p.name}")

    print(f"\nDone. {len(records)} card(s) in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
