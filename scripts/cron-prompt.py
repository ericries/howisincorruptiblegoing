#!/usr/bin/env python3
"""Read a cron job's prompt out of docs/CRONS.md.

    python3 scripts/cron-prompt.py morning-scan
    python3 scripts/cron-prompt.py --list

This exists to flip the direction of a dependency that kept failing. Until
2026-10-21 the watchdog carried each job's LIVE in-memory prompt forward on every
roll, and CRONS.md was meant to be re-synced by hand afterwards. It never kept
up: on 2026-10-21 all seven sections had drifted behind the live prompts, and an
earlier commit message had claimed a CRONS.md edit that silently failed.

The deeper problem was not tidiness. A lesson learned during a scan lived only in
an in-memory cron, so it died when the session ended — the repo is supposed to be
the thing that survives a change of platform, and the prompts were the one part
that did not.

Now the watchdog reads from here. A lesson has to be written into CRONS.md to
survive the next roll, which puts it in version control by construction.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "CRONS.md"

# `heading` is matched against the "## N. Title — `cron`" lines; `signature` is a
# phrase that must appear inside that job's own prompt, so a mis-pasted block is
# caught by the tests rather than by rescheduling the wrong work.
JOBS: dict[str, dict] = {
    "watchdog":        {"heading": "## 1. Watchdog",          "cron": "17 8 * * *",
                        "signature": "Cron watchdog. Run CronList"},
    "morning-scan":    {"heading": "## 2. Morning content scan", "cron": "7 9 * * *",
                        "signature": "Morning content scan"},
    "goodreads":       {"heading": "## 3. Goodreads review scan", "cron": "33 10 * * 1",
                        "signature": "Goodreads review scan"},
    "comment-archive": {"heading": "## 4. LinkedIn comment archive", "cron": "47 10 * * 1,3,5",
                        "signature": "comment archive scan"},
    "recall-audit":    {"heading": "## 5. Weekly LinkedIn recall audit", "cron": "17 11 * * 0",
                        "signature": "Weekly LinkedIn recall audit"},
    "evening-scan":    {"heading": "## 6. Evening content scan", "cron": "3 18 * * *",
                        "signature": "Evening content scan"},
    "sidebar":         {"heading": "## 7. Sidebar curation",  "cron": "27 19 * * *",
                        "signature": "Sidebar curation"},
}

_FENCE = re.compile(r"```\n(.*?)\n```", re.S)


def prompt_for(job: str, doc: Path = DOC) -> str:
    """The fenced prompt body for `job`, verbatim and without the fences."""
    spec = JOBS[job]                      # KeyError on an unknown job, deliberately
    text = Path(doc).read_text()
    start = text.index(spec["heading"])
    nxt = text.find("\n## ", start + 1)
    section = text[start: nxt if nxt != -1 else len(text)]
    m = _FENCE.search(section)
    if not m:
        raise ValueError(f"no fenced prompt block in section for {job!r}")
    return m.group(1)


def schedule_table(doc: Path = DOC) -> dict[str, str]:
    """Map each job heading to the cron expression in its own `## N. …` line."""
    out: dict[str, str] = {}
    for line in Path(doc).read_text().splitlines():
        if not line.startswith("## "):
            continue
        m = re.match(r"(## \d+\. [^—]+?)\s+—\s+`([^`]+)`", line)
        if m:
            out[m.group(1).strip()] = m.group(2)
    return out


def _main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--list", "-l"):
        for job, spec in JOBS.items():
            print(f"{job:16s} {spec['cron']}")
        return 0
    job = argv[0]
    if job not in JOBS:
        print(f"unknown job {job!r}; try --list", file=sys.stderr)
        return 2
    sys.stdout.write(prompt_for(job))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
