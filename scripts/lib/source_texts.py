"""Full-source archive for published entries.

The site publishes a `blockquote` — deliberately a subset of what someone wrote.
This module keeps the *complete* source text on disk, keyed by entry id, so we
can re-read a review in full, pull a different quote later, or check that a
published excerpt is faithful, without re-scraping a page that may be gone.

Local only: `data/archive/` is gitignored and never shipped to the site.

Guarantees the tests pin:
  - text is stored verbatim; never truncated, never re-wrapped
  - capture is idempotent
  - a later, shorter capture never clobbers a longer one already held
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / "data" / "archive" / "source-texts"

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_path(entry_id: str) -> Path:
    """Path for an entry's record. Rejects ids that aren't safe as filenames —
    entry ids come from scan data, so a `../` must not escape the archive dir."""
    if not entry_id or not _SAFE_ID.match(entry_id):
        raise ValueError(f"unsafe entry id for a filename: {entry_id!r}")
    return ARCHIVE_DIR / f"{entry_id}.json"


def load(entry_id: str) -> dict | None:
    path = record_path(entry_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def has(entry_id: str) -> bool:
    return record_path(entry_id).exists()


def capture(
    entry_id: str,
    *,
    source_url: str,
    full_text: str,
    author: str | None = None,
    platform: str | None = None,
    captured_at: str | None = None,
) -> Path:
    """Store the complete source text for `entry_id`.

    Re-capturing is safe: identical text is a no-op, longer text upgrades the
    record, and shorter text is ignored so a scan that only re-reads the
    published excerpt can't shrink what we hold.
    """
    if not (full_text or "").strip():
        raise ValueError("full_text is empty — refusing to record an empty source")

    path = record_path(entry_id)
    existing = load(entry_id)

    if existing and len(existing.get("full_text") or "") >= len(full_text):
        return path  # already hold this much or more; leave it alone

    rec = {
        "entry_id": entry_id,
        "source_url": source_url,
        "platform": platform,
        "author": author,
        # earliest capture wins — this is when we first saw the text
        "captured_at": (existing or {}).get("captured_at") or captured_at or _now(),
        "chars": len(full_text),
        "full_text": full_text,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def missing(entries: list[dict]) -> list[str]:
    """Entry ids with no full source text captured yet, in input order."""
    out = []
    for e in entries:
        eid = e.get("id")
        if not eid:
            continue
        try:
            if not has(eid):
                out.append(eid)
        except ValueError:
            out.append(eid)
    return out


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def contains_blockquote(entry_id: str, blockquote: str) -> bool:
    """Whether the published excerpt appears in the stored source, ignoring
    whitespace differences. Used to spot excerpts that drifted from the source."""
    rec = load(entry_id)
    if not rec:
        return False
    return _squash(blockquote) in _squash(rec.get("full_text") or "")
