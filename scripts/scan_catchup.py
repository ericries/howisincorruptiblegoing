"""Which scheduled scan runs were missed, and are therefore owed work.

These crons only fire while the REPL is idle. A shut laptop skips a cycle with no
error anywhere; a long-running turn swallows any slot it overlaps. Both happened
in the week of 2026-10-20.

`scan-coverage.py` already asks "did source X produce an archive file on day Y".
That is the wrong question twice over:

  - It does not know each job's cadence, so every day looks like a day the job
    owed work. Reading its output on 2026-10-20 I reported the Monday-only
    Goodreads scan and the Mon/Wed/Fri comment archive as missed. It was a
    Tuesday; neither was due, and re-running them cost real Apify budget.
  - It is wired only into the watchdog at 8:17, which runs before the day's work
    and so can never see that day's failures.

This module asks instead: which scheduled fire times have passed without the job
running? That question can be answered by any turn — a cron, a session start, or
Eric asking — so catch-up stops depending on one particular cron still being
alive, which is the thing that keeps failing.

Everything here is pure computation over the cron expression and the watermark.
It makes no network calls and costs nothing to run.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan_state import read_watermark  # noqa: E402

UTC = _dt.timezone.utc

# Jitter allows a recurring job to fire up to 15 minutes late, and it cannot fire
# at all while a turn is in progress. Reporting a slot as missed the moment it
# passes would flag jobs that are merely about to run.
DEFAULT_GRACE_MINUTES = 20

# A three-month outage should not queue ninety scans. One catch-up with a widened
# postedLimit (scan_state.choose_posted_limit) covers the whole gap, so there is
# nothing to gain from enumerating every slot — and a lot of budget to lose.
DEFAULT_MAX_REPORTED = 5

# Mirrors the deployed crons; keep in step with docs/CRONS.md. `source` is the
# scan_state watermark key that proves the job ran.
JOBS: dict[str, dict] = {
    "morning-scan":    {"cron": "7 9 * * *",      "source": "linkedin-keyword",
                        "label": "Morning content scan"},
    "evening-scan":    {"cron": "3 18 * * *",     "source": "linkedin-mentions",
                        "label": "Evening content scan"},
    "goodreads":       {"cron": "33 10 * * 1",    "source": "goodreads",
                        "label": "Goodreads review scan (Mondays)"},
    "comment-archive": {"cron": "47 10 * * 1,3,5", "source": "linkedin-comments",
                        "label": "LinkedIn comment archive (Mon/Wed/Fri)"},
}


# --- cron expression ----------------------------------------------------------------

def _parse(expr: str) -> tuple[int, int, set[int]]:
    """(minute, hour, weekdays) for the subset of cron these jobs use.

    Day-of-month and month are always "*" here; a job that needed them would be a
    new shape and should fail loudly rather than be silently mis-scheduled.
    """
    minute, hour, dom, month, dow = expr.split()
    if dom != "*" or month != "*":
        raise ValueError(f"unsupported cron (day-of-month/month must be *): {expr!r}")
    days = set(range(7)) if dow == "*" else {int(d) % 7 for d in dow.split(",")}
    return int(minute), int(hour), days


def _cron_weekday(d: _dt.date) -> int:
    """Cron numbers Sunday 0; Python numbers Monday 0."""
    return (d.weekday() + 1) % 7


def _slots(expr: str, start: _dt.datetime, end: _dt.datetime):
    """Every fire time of `expr` in (start, end], oldest first."""
    minute, hour, days = _parse(expr)
    day = start.date()
    while day <= end.date():
        if _cron_weekday(day) in days:
            t = _dt.datetime.combine(day, _dt.time(hour, minute), tzinfo=start.tzinfo)
            if start < t <= end:
                yield t
        day += _dt.timedelta(days=1)


def next_run_after(expr: str, when: _dt.datetime) -> _dt.datetime:
    """The first fire time strictly after `when`. Used to describe the schedule."""
    for t in _slots(expr, when, when + _dt.timedelta(days=8)):
        return t
    raise ValueError(f"no run within 8 days for {expr!r}")


# --- the question that matters ------------------------------------------------------

def missed_runs(expr: str, last_seen: _dt.datetime | None, now: _dt.datetime,
                *, grace_minutes: int = DEFAULT_GRACE_MINUTES,
                max_reported: int = DEFAULT_MAX_REPORTED) -> list[_dt.datetime]:
    """Fire times that have passed (plus grace) since `last_seen` without running.

    `last_seen` is when the job last actually completed, not when it was due — a
    job that fired at 09:39 for its 09:07 slot has covered that slot.

    Returns the most recent `max_reported` slots. A never-run job returns at most
    its latest due slot: there is no backlog to replay, only work to start.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    cutoff = now - _dt.timedelta(minutes=grace_minutes)

    if last_seen is None:
        start = now - _dt.timedelta(days=8)
        slots = [t for t in _slots(expr, start, cutoff)]
        return slots[-1:]

    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if last_seen >= now:          # clock skew: nothing is owed
        return []

    # Step back to the slot `last_seen` was covering, so a late run still counts.
    minute, hour, _ = _parse(expr)
    slot_of_last = last_seen.replace(hour=hour, minute=minute, second=0, microsecond=0)
    anchor = slot_of_last if slot_of_last <= last_seen else last_seen

    slots = [t for t in _slots(expr, anchor, cutoff)]
    return slots[-max_reported:]


# --- applying it to the deployed jobs -----------------------------------------------

def overdue(now: _dt.datetime | None = None, jobs: dict | None = None,
            tz: _dt.tzinfo | None = None) -> list[dict]:
    """Every job owing work, with the slots it missed. Empty list is the happy path.

    Cron expressions are in the machine's LOCAL time (that is what CronCreate
    schedules against) while watermarks are written in UTC, so both sides are
    converted to local before being compared. Skipping that conversion shifts
    every slot by the UTC offset — on the first live run it turned the 18:03
    evening scan into an 11:03 slot that looked missed at noon.
    """
    now = now or _dt.datetime.now(UTC)
    tz = tz or _dt.datetime.now().astimezone().tzinfo
    now = now.astimezone(tz)
    out = []
    for name, spec in (jobs or JOBS).items():
        wm = read_watermark(spec["source"])
        last = None
        if wm:
            try:
                last = _dt.datetime.fromisoformat(str(wm).replace("Z", "+00:00")).astimezone(tz)
            except ValueError:
                last = None
        slots = missed_runs(spec["cron"], last, now)
        if slots:
            out.append({"job": name, "label": spec["label"], "source": spec["source"],
                        "last_seen": wm, "missed": slots})
    return out


def _main() -> int:
    # Local-aware, because the cron expressions are local. Passing a UTC `now`
    # here built the slots in UTC and then shifted them again on display, which
    # printed the 9:07 morning scan as "next Wed 02:07".
    now = _dt.datetime.now().astimezone()
    rows = overdue(now)
    if not rows:
        print("Catch-up: nothing overdue.")
        for name, spec in JOBS.items():
            nxt = next_run_after(spec["cron"], now)
            print(f"  {name:16s} next {nxt:%a %H:%M}")
        return 0
    print(f"Catch-up: {len(rows)} job(s) owe work.")
    for r in rows:
        when = ", ".join(t.astimezone().strftime("%a %d %H:%M") for t in r["missed"])
        print(f"  {r['job']:16s} last ran {r['last_seen'] or 'never'}")
        print(f"  {'':16s} missed: {when}")
    print("\nRun each with a derived postedLimit (scan_state.choose_posted_limit)")
    print("and dedup client-side against data/archive/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
