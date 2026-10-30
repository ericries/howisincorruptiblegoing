"""Did consecutive feed pulls meet, or is there a day neither of them saw?

    python3 scripts/feed_coverage.py            # every lane, holes + starvation
    python3 scripts/feed_coverage.py --lane author

`scan_catchup` answers "did the job run". This answers the different question of
whether the pull it made reached back far enough to touch the previous one. Both
times the comment archive lost a day — 2026-10-24 and 2026-10-27 — the job ran on
schedule and wrote its watermark, so catch-up said "nothing overdue" and was
right. The loss was invisible to every check that existed.

The mechanism, measured rather than assumed (docs/postmortems/2026-10-28):

  harvestapi/linkedin-post-search emits one interleaved stream — a post, then its
  comments, then the next post. `callOptions.maxItems` truncates that stream by
  TOTAL items, so comments on early posts consume the budget that later posts
  needed. On 2026-10-28 a cap of 40 reached only the 6th post of a requested 30,
  and the pull covered a single day instead of a week.

So two things are worth reporting, and they are not the same:

  holes      — a date no run's post range covered. Already lost; only a wider
               postedLimit re-pull can recover it.
  starvation — a run that hit its item cap while still short of its post quota.
               The leading indicator: it says the NEXT run is likely to leave a
               hole, while the cap is still cheap to raise.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "archive" / "linkedin-raw"

# Which raw files belong to which lane. The comment-archive job writes both, and
# a hole in one is not a hole in the other — they search different things, so
# they truncate at different places and must be compared separately.
# A `recovery` pull — the re-pull you make once a hole is found — belongs to the
# lane it repairs. Leaving it out meant the tool kept reporting a hole that had
# already been filled, which is how you train someone to stop reading the output.
LANES: dict[str, str] = {
    "author": r"-(?:comments|recovery)-author\.json$",
    "keyword": r"-(?:comments|recovery)-keyword\.json$",
}

# What the cron currently asks for, so starvation can be judged without the
# caller having to know. Keep in step with docs/CRONS.md.
LANE_REQUEST: dict[str, dict[str, int]] = {
    "author": {"cap": 400, "max_posts": 50},
    "keyword": {"cap": 400, "max_posts": 50},
}

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


# --- reading a raw dataset ----------------------------------------------------------

def _date_of(item: dict) -> str | None:
    """The YYYY-MM-DD a post was published, from either postedAt shape."""
    posted = item.get("postedAt")
    if isinstance(posted, dict):
        posted = posted.get("date")
    if not isinstance(posted, str):
        return None
    m = _DATE_RE.match(posted)
    return m.group(1) if m else None


def post_dates(items: list[dict]) -> list[str]:
    """Dates of the POST items, oldest first.

    harvestapi distinguishes the two kinds by presence of `author`: posts carry
    one, comment records do not. Counting items instead of posts is the exact
    misreading that put a total-item cap on this call (see the 10-14 regression
    test in test_feed_coverage.py).
    """
    return sorted(d for d in (_date_of(i) for i in items if i.get("author")) if d)


def run_span(items: list[dict]) -> tuple[str, str] | None:
    """(oldest, newest) post date in one pull, or None if it returned no posts."""
    dates = post_dates(items)
    return (dates[0], dates[-1]) if dates else None


# --- comparing consecutive pulls ----------------------------------------------------

def _days_between(after: str, before: str) -> list[str]:
    """Dates strictly between two YYYY-MM-DD bounds, exclusive both ends."""
    a = _dt.date.fromisoformat(after)
    b = _dt.date.fromisoformat(before)
    out, d = [], a + _dt.timedelta(days=1)
    while d < b:
        out.append(d.isoformat())
        d += _dt.timedelta(days=1)
    return out


def find_holes(runs: list[dict]) -> list[dict]:
    """Dates that NO pull covered, anywhere in the lane's overall range.

    `runs` is chronological, each {"file": str, "span": (oldest, newest) | None}.
    A pull with no posts is skipped rather than treated as a boundary: it covered
    nothing, so it neither creates a hole nor closes one. Comparing against it
    would invent a hole on any quiet day.

    This asks whether ANY run covered a date, not whether each run reached the
    one before it. The pairwise version was wrong in a way that only showed up
    once it was used: after re-pulling 2026-10-27 with a week-wide recovery pull,
    it still reported the hole, because the original consecutive pair still
    failed to meet. A hole that has been filled must stop being reported — an
    alarm that stays on after the fix is an alarm you learn to ignore.
    """
    covering = [r for r in runs if r.get("span")]
    if len(covering) < 2:
        return []

    covered: set[str] = set()
    for r in covering:
        lo, hi = r["span"]
        covered.add(lo)
        covered.update(_days_between(lo, hi))
        covered.add(hi)

    lo = min(r["span"][0] for r in covering)
    hi = max(r["span"][1] for r in covering)
    missing = [d for d in _days_between(lo, hi) if d not in covered]
    if not missing:
        return []

    # Group consecutive missing dates, and attribute each block to the runs that
    # bracket it, so the report names files rather than bare dates.
    holes, block = [], [missing[0]]
    for d in missing[1:]:
        is_next_day = _dt.date.fromisoformat(d) - _dt.date.fromisoformat(block[-1]) \
            == _dt.timedelta(days=1)
        if is_next_day:
            block.append(d)
        else:
            holes.append(block)
            block = [d]
    holes.append(block)

    out = []
    for blk in holes:
        before = min((r for r in covering if r["span"][0] > blk[-1]),
                     key=lambda r: r["span"][0], default=None)
        after = max((r for r in covering if r["span"][1] < blk[0]),
                    key=lambda r: r["span"][1], default=None)
        out.append({"after": after["file"] if after else None,
                    "before": before["file"] if before else None,
                    "dates": blk})
    return out


# A capped run does not land exactly on the cap. Every truncated pull in the
# archive returned 39 or 40 against a cap of 40 — the actor stops once the next
# batch would overshoot, so it lands at or just under. Requiring `n_items >= cap`
# exactly would have scored the 39-item runs as healthy, which is most of them.
CAP_TOLERANCE = 2


def is_starved(*, n_items: int, n_posts: int, cap: int, max_posts: int) -> bool:
    """Did the item cap cut this pull short of the posts it asked for?

    Both conditions are needed. At the cap with the quota met, the cap cost
    nothing. Short of quota but under the cap just means Eric posted less that
    week — truncation is not the explanation, and calling it one would send
    someone to raise a limit that was never binding.
    """
    return n_items >= cap - CAP_TOLERANCE and n_posts < max_posts


# --- walking the archive ------------------------------------------------------------

def lane_runs(lane: str, raw: Path = RAW) -> list[dict]:
    """Every pull in one lane, chronological, with its span and item counts."""
    pattern = re.compile(LANES[lane])
    out = []
    for f in sorted(raw.glob("*.json")):
        if not pattern.search(f.name):
            continue
        try:
            items = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(items, list):
            continue
        out.append({
            "file": f.name,
            "span": run_span(items),
            "n_items": len(items),
            "n_posts": len(post_dates(items)),
        })
    return out


def report(lanes: list[str] | None = None, raw: Path = RAW) -> tuple[list[str], int]:
    """(lines, n_problems) — safe to print unconditionally at session start."""
    lines, problems = [], 0
    for lane in lanes or list(LANES):
        runs = lane_runs(lane, raw)
        if not runs:
            continue
        req = LANE_REQUEST.get(lane, {"cap": 250, "max_posts": 50})
        holes = find_holes(runs)
        starved = [r for r in runs
                   if is_starved(n_items=r["n_items"], n_posts=r["n_posts"],
                                 cap=req["cap"], max_posts=req["max_posts"])]
        if not holes and not starved:
            last = runs[-1]
            span = f"{last['span'][0]}..{last['span'][1]}" if last["span"] else "no posts"
            lines.append(f"  {lane:8s} clean — last pull {last['n_posts']} posts, {span}")
            continue
        for h in holes:
            problems += 1
            lines.append(f"  {lane:8s} HOLE {', '.join(h['dates'])} "
                         f"— between {h['after']} and {h['before']}")
        for r in starved:
            problems += 1
            lines.append(f"  {lane:8s} STARVED {r['file']} — {r['n_items']} items hit the "
                         f"{req['cap']} cap with only {r['n_posts']}/{req['max_posts']} posts")
    return lines, problems


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lane", choices=sorted(LANES), action="append",
                    help="limit to one lane (repeatable); default is all")
    args = ap.parse_args()

    lines, problems = report(args.lane)
    if not lines:
        print("Feed coverage: no raw pulls on disk to check.")
        return 0
    print(f"Feed coverage: {problems} problem(s)." if problems else "Feed coverage: clean.")
    for line in lines:
        print(line)
    if problems:
        print("\nA HOLE is already lost — re-pull with a wider postedLimit to recover it.")
        print("STARVED means the cap bound before the post quota was met; raise")
        print("callOptions.maxItems in docs/CRONS.md before the next run leaves a hole.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
