"""Scan state: self-healing windows, orphaned-run recovery, coverage-gap detection.

The scanner runs on Claude Code session crons, which only fire while the REPL is
idle. A closed laptop means a cycle simply does not happen. Every piece of this
module exists because the pipeline previously assumed a cadence the environment
does not guarantee:

  - Daily scans hardcoded `postedLimit: "24h"`. When a day was skipped the next
    run's window never reached back over the gap, so the posts in it were lost
    silently. On 2026-10-12 that cost three posts at 108, 81 and 68 reactions.
    `choose_posted_limit` derives the window from the last successful scan
    instead, so a missed day widens the next pull rather than dropping it.

  - On 2026-10-15 a turn launched six Apify runs and then ended before triage.
    The dataset ids existed only in conversation context. `record_run` puts them
    on disk at launch so the next turn can find and finish them — the data is
    already paid for either way.

  - Nothing noticed either condition until a human asked. `coverage_gaps` makes
    the check mechanical so the watchdog can run it.

All helpers degrade to a safe default rather than raising: a scan that cannot
read its own state should still run, just more broadly than strictly necessary.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "archive" / ".scan-state.json"
PENDING_PATH = REPO / "data" / "archive" / ".pending-runs.json"

# postedLimit values the harvestapi actor accepts. "7d" fails validation.
VALID_WINDOWS = ("any", "1h", "24h", "week", "month", "3months", "6months", "year")

# A daily cron never fires at exactly 24h intervals: the scheduler adds jitter
# (up to 10% of the period), and a cron only fires once the REPL is idle, so a
# late-opened laptop pushes it later still. Treating any gap over 24h as an
# outage would widen to "week" every single day and erase the cost saving, so
# gaps up to this are considered on schedule.
#
# The tradeoff this accepts: when a run is late by N minutes, an N-minute sliver
# at the far edge of the previous window goes uncovered. That is a real but
# small hole — the Sunday recall audit runs a full week at maxPosts=100 and is
# the designed backstop for anything that slips through it.
ON_SCHEDULE_DAYS = 1.25


# --- internals ---------------------------------------------------------------------

def _load(path: Path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        # Missing or corrupt state must not take the scan down with it.
        return default


def _save(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)  # atomic: a half-written state file is worse than none


def _parse(ts: str) -> _dt.datetime | None:
    if not ts:
        return None
    try:
        return _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


# --- self-healing window -----------------------------------------------------------

def choose_posted_limit(last_scan: str | None, now: str) -> str:
    """Smallest actor window that still reaches back to `last_scan`.

    On schedule this returns "24h" and costs what it always did. After a missed
    day it returns "week", after a missed week "month" — the pull widens exactly
    as much as the outage requires and no more, which matters on a capped budget.
    Always pair a widened window with client-side dedup against the archive.
    """
    start, end = _parse(last_scan), _parse(now)
    if start is None or end is None:
        return "week"  # never scanned, or unparseable: cover a week, not a month
    gap_days = (end - start).total_seconds() / 86400.0
    if gap_days <= ON_SCHEDULE_DAYS:
        return "24h"  # includes clock skew / negative gaps
    if gap_days <= 7:
        return "week"
    if gap_days <= 30:
        return "month"
    return "3months"


def read_watermark(source: str, path: Path = STATE_PATH) -> str | None:
    """Last successful scan timestamp for `source`, or None if never scanned."""
    return _load(Path(path), {}).get(source)


def write_watermark(source: str, when: str, path: Path = STATE_PATH) -> None:
    """Record a successful scan. Call only after the dataset is archived."""
    state = _load(Path(path), {})
    state[source] = when
    _save(Path(path), state)


# --- orphaned run recovery ---------------------------------------------------------

def record_run(dataset_id: str, *, actor: str, label: str, launched_at: str,
               path: Path = PENDING_PATH) -> None:
    """Note a launched Apify run on disk, immediately after launching it.

    If the turn dies before triage, the next turn can still find the dataset.
    """
    runs = _load(Path(path), [])
    if any(r.get("dataset_id") == dataset_id for r in runs):
        return
    runs.append({"dataset_id": dataset_id, "actor": actor, "label": label,
                 "launched_at": launched_at})
    _save(Path(path), runs)


def list_pending(path: Path = PENDING_PATH) -> list[dict]:
    """Runs launched but not yet marked triaged."""
    runs = _load(Path(path), [])
    return runs if isinstance(runs, list) else []


def clear_run(dataset_id: str, path: Path = PENDING_PATH) -> None:
    """Mark a run triaged. Unknown ids are ignored."""
    runs = [r for r in list_pending(path) if r.get("dataset_id") != dataset_id]
    _save(Path(path), runs)


# --- coverage gaps -----------------------------------------------------------------

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_NON_DAILY = ("catchup", "audit")


def _as_rule(spec) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Normalise a source spec to (include_substrings, exclude_substrings)."""
    if isinstance(spec, str):
        return ((spec,), ())
    inc, exc = spec
    if isinstance(inc, str):
        inc = (inc,)
    if isinstance(exc, str):
        exc = (exc,)
    return tuple(inc), tuple(exc)


def coverage_gaps(archive_dir, start: str, end: str, sources: dict
                  ) -> list[tuple[str, list[str]]]:
    """Days in [start, end] where a daily source produced no archive file.

    `sources` maps a label to either a filename substring, or a pair of
    (include_substrings, exclude_substrings). Exclusions matter because one job's
    output can look like another's: the daily keyword scan has written both
    "keyword-24h.json" and "kw-ries.json" over time, while the Mon/Wed/Fri
    comment archive writes "keyword-week-comments.json" — which must not be
    allowed to mask a missing daily scan.

    Catch-up and audit pulls are excluded throughout: a backfill should not make
    a genuine daily hole look covered.
    """
    d = Path(archive_dir)
    rules = {label: _as_rule(spec) for label, spec in sources.items()}
    present: dict[str, set[str]] = {}
    if d.is_dir():
        for f in d.iterdir():
            m = _DATE_RE.match(f.name)
            if not m or any(tok in f.name for tok in _NON_DAILY):
                continue
            for label, (inc, exc) in rules.items():
                if any(tok in f.name for tok in exc):
                    continue
                if not inc or any(tok in f.name for tok in inc):
                    present.setdefault(m.group(1), set()).add(label)

    out: list[tuple[str, list[str]]] = []
    day = _dt.date.fromisoformat(start)
    last = _dt.date.fromisoformat(end)
    while day <= last:
        iso = day.isoformat()
        missing = sorted(set(sources) - present.get(iso, set()))
        if missing:
            out.append((iso, missing))
        day += _dt.timedelta(days=1)
    return out
