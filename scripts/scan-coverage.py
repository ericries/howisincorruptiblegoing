#!/usr/bin/env python3
"""Report scan-coverage holes and orphaned Apify runs. Read-only, no API cost.

The scanner runs on session crons that only fire while the REPL is idle, so a
closed laptop produces days with no scan. Nothing used to detect that: on
2026-10-12 the evening @-mention pull never ran and three posts (108, 81 and 68
reactions) sat unseen until a human thought to ask. This makes the check
mechanical.

Usage:
    python3 scripts/scan-coverage.py              # last 14 days
    python3 scripts/scan-coverage.py --days 30
"""

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_state import coverage_gaps, is_gap_acked, list_pending  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# label -> filename substring written by each daily job
LINKEDIN_SOURCES = {
    # the daily keyword scan has used two filename shapes; the Mon/Wed/Fri
    # comment archive writes "keyword-week-comments" and must not count
    "keyword": (("kw-", "keyword"), ("comments", "week")),
    "mentions": (("mentions",), ("comments",)),
}
OTHER = {
    "twitter-raw": {"twitter": ""},
    "youtube-raw": {"youtube": ""},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()

    end = _dt.date.today()
    start = end - _dt.timedelta(days=args.days - 1)

    problems = 0

    gaps = coverage_gaps(REPO / "data/archive/linkedin-raw",
                         start.isoformat(), end.isoformat(), LINKEDIN_SOURCES)
    # today is still in progress; a hole today is not yet a miss
    gaps = [g for g in gaps if g[0] != end.isoformat()]
    print(f"LinkedIn coverage, {start} .. {end}")
    acked_n = 0
    open_gaps = []
    for day, missing in gaps:
        live = [m for m in missing if not is_gap_acked(m, day)]
        acked_n += len(missing) - len(live)
        if live:
            open_gaps.append((day, live))
    if open_gaps:
        problems += len(open_gaps)
        for day, missing in open_gaps:
            print(f"  GAP  {day}  missing: {', '.join(missing)}")
    else:
        print("  no open gaps")
    if acked_n:
        print(f"  ({acked_n} earlier gap(s) acknowledged as backfilled — "
              f"see data/archive/.gap-acks.json)")

    for sub, sources in OTHER.items():
        g = coverage_gaps(REPO / "data/archive" / sub,
                          start.isoformat(), end.isoformat(), sources)
        g = [x for x in g if x[0] != end.isoformat()]
        label = sub.replace("-raw", "")
        g = [x for x in g if not all(is_gap_acked(m, x[0]) for m in x[1])]
        if g:
            problems += len(g)
            print(f"{label}: {len(g)} day(s) with no pull — "
                  f"{', '.join(d for d, _ in g[:8])}")
        else:
            print(f"{label}: no gaps")

    pending = list_pending()
    if pending:
        problems += len(pending)
        print(f"\nORPHANED Apify runs ({len(pending)}) — launched, never triaged:")
        for r in pending:
            print(f"  {r.get('dataset_id')}  {r.get('label')}  "
                  f"launched {r.get('launched_at')}  [{r.get('actor')}]")
        print("  These datasets are already paid for. Triage them before new pulls.")
    else:
        print("\nno orphaned Apify runs")

    if problems:
        print(f"\n{problems} issue(s). Backfill a gap with a widened postedLimit "
              f"(scan_state.choose_posted_limit) and dedup against the archive.")
    return 0  # advisory only: never block a cron on this


if __name__ == "__main__":
    raise SystemExit(main())
