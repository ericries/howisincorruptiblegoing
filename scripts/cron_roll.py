#!/usr/bin/env python3
"""Hand a cron prompt over, and leave a trace of what was handed over.

    python3 scripts/cron_roll.py <job>            # print the prompt + its ROLL TOKEN, and log it
    python3 scripts/cron_roll.py --check          # which sections have drifted from their last roll
    python3 scripts/cron_roll.py --rolled <job> <bytes>   # confirm what you actually passed to CronCreate

WHY THIS EXISTS

The watchdog's premise is that `docs/CRONS.md` outlives the session. Three
times the file was found BEHIND the live crons — 2026-10-25, 2026-10-26 and
2026-11-01, the last by seven whole passages — because a roll improved a prompt
in flight and the improvement was never written back. Each repair was a commit
titled "write back the lessons the roll carried forward": the instance fix,
performed three times, with no mechanism built in between.

A true live-vs-file comparison is impossible — `CronList` returns an ~80
character preview, so the text inside a running cron cannot be read back. What
can be done is make the handover leave evidence:

  * `cron_roll.py <job>` is the only sanctioned way to get the text, and it
    records the sha and byte count of exactly what it printed.
  * It prints a ROLL TOKEN. The watchdog reports one per job, so the number
    that should match is written down in two places.
  * `--rolled <job> <bytes>` compares what you actually passed to CronCreate
    against that token. A mismatch is an enrichment that has not been written
    back, named at the moment it happens rather than discovered a week later.
  * `--check` catches the opposite drift: a section edited since its last roll,
    meaning the live cron is now behind the repo.

See docs/postmortems/2026-11-01-the-repo-fell-behind-the-crons-again.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "cron-roll-log.json"

JOBS = ["watchdog", "morning-scan", "goodreads", "comment-archive",
        "recall-audit", "evening-scan", "sidebar"]

#: Enough history to see a pattern, bounded so the log stays readable.
KEEP_ROLLS = 10


def digest(text: str) -> dict:
    """sha and SIZE IN BYTES — `wc -c` counts bytes, and mixing the two with
    character counts made the watchdog's size diff lie on 2026-11-01."""
    raw = text.encode("utf-8")
    return {"sha12": hashlib.sha256(raw).hexdigest()[:12], "bytes": len(raw)}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def record(job: str, text: str, rolled_at: str, path: Path = LOG) -> dict:
    d = digest(text)
    data = _load(path)
    entry = {"rolled_at": rolled_at, **d}
    data.setdefault(job, []).append(entry)
    data[job] = data[job][-KEEP_ROLLS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(data.items())), indent=2) + "\n")
    return entry


def check(current: dict[str, str], path: Path = LOG) -> dict:
    """Compare each job's current file text against its last recorded roll."""
    data = _load(path)
    out = {}
    for job, text in current.items():
        rolls = data.get(job) or []
        if not rolls:
            out[job] = {"status": "never-rolled", "detail": "no roll recorded"}
            continue
        last = rolls[-1]
        now = digest(text)
        if now["sha12"] == last["sha12"]:
            out[job] = {"status": "in-sync", "detail": f"rolled {last['rolled_at']}"}
        else:
            out[job] = {
                "status": "file-ahead",
                "detail": (f"CRONS.md changed since the {last['rolled_at']} roll "
                           f"({last['bytes']} -> {now['bytes']} bytes); the live "
                           f"cron is behind the repo until it is rolled again"),
            }
    return out


def verify_rolled(job: str, rolled_bytes: int, path: Path = LOG) -> str:
    """Did what you passed to CronCreate match what the repo handed you?"""
    rolls = (_load(path).get(job) or [])
    if not rolls:
        return f"never-rolled: no token recorded for {job}"
    last = rolls[-1]
    if rolled_bytes == last["bytes"]:
        return "ok"
    delta = rolled_bytes - last["bytes"]
    return (f"ENRICHED: you rolled {rolled_bytes} bytes against a token of "
            f"{last['bytes']} ({delta:+d}). That text exists only in the live "
            f"cron and dies with this session — patch docs/CRONS.md with the "
            f"addition, commit it, then re-run `cron_roll.py {job}` for a fresh "
            f"token.")


def prompt_text(job: str) -> str:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "cron-prompt.py"), job],
                         capture_output=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr.decode() or f"cron-prompt.py failed for {job}")
    return out.stdout.decode("utf-8")


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", nargs="?", choices=JOBS)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rolled", nargs=2, metavar=("JOB", "BYTES"))
    args = ap.parse_args()

    if args.rolled:
        job, n = args.rolled[0], int(args.rolled[1])
        verdict = verify_rolled(job, n)
        print(verdict)
        return 0 if verdict == "ok" else 1

    if args.check:
        rows = check({j: prompt_text(j) for j in JOBS})
        worst = 0
        for job in JOBS:
            r = rows[job]
            mark = {"in-sync": "✓", "file-ahead": "!", "never-rolled": "·"}[r["status"]]
            print(f" {mark} {job:16s} {r['status']:13s} {r['detail']}")
            if r["status"] == "file-ahead":
                worst = 1
        return worst

    if not args.job:
        ap.error("give a job name, --check, or --rolled JOB BYTES")

    text = prompt_text(args.job)
    now = _dt.datetime.now(_dt.UTC).replace(microsecond=0, tzinfo=None).isoformat() + "Z"
    entry = record(args.job, text, now)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    print(f"\n--- ROLL TOKEN {args.job} {entry['sha12']} {entry['bytes']} bytes ---")
    print("Pass the text ABOVE this line to CronCreate verbatim. If you change so "
          "much as a word, patch docs/CRONS.md and re-run this command instead — "
          "an edit made here dies with the session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
