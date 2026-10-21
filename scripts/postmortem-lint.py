#!/usr/bin/env python3
"""Check that a postmortem invests in prevention at every level it reached.

    python3 scripts/postmortem-lint.py            # all postmortems since the rule
    python3 scripts/postmortem-lint.py <file.md>

Eric, 2026-10-21: "do these root cause analyses routinely, always make
proportional investments in prevention at each level."

Writing five whys is the easy half. The prevention table is where the investment
is either made or quietly skipped — a postmortem that reaches depth five and then
ships only the level-one instance fix looks thorough and changes nothing. So the
table is the part that gets checked, not the prose.

It also rejects a prevention whose text is "remember to X". That is the instance
fix wearing a hat, and it is the exact pattern the 2026-10-21 postmortem was
about: the watchdog prompt told me to re-sync a file by hand, which made the
workaround the official process.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "docs" / "postmortems"

# The date the rule starts. Retrofitting the back catalogue is a separate job;
# failing on it every run would just train me to ignore the output.
RULE_START = "2026-10-21"

VALID_STATUS = {"shipped", "open", "declined", "no change needed"}

_WHY_RE = re.compile(r"^\*\*(\d+)[a-z]?\.\s", re.M)
_ROW_RE = re.compile(r"^\|\s*(\d+)\s*[—-].*?\|(.*?)\|(.*?)\|(.*?)\|\s*$", re.M)
_REMEMBER_RE = re.compile(
    r"\b(remember to|be sure to|don'?t forget|make sure to|try to remember)\b", re.I)


def check(text: str, *, is_template: bool = False) -> list[str]:
    """Problems with one postmortem's prevention table. Empty list means fine."""
    if is_template:
        return []

    problems: list[str] = []
    whys = {int(m.group(1)) for m in _WHY_RE.finditer(text)}
    n_whys = len(whys)

    if "## Prevention" not in text:
        problems.append(
            f"no prevention table — {n_whys} whys reached and nothing recorded against them")
        return problems

    table = text.split("## Prevention", 1)[1]
    rows = _ROW_RE.findall(table)
    if not rows:
        problems.append("prevention section has no table rows")
        return problems

    if len(rows) < n_whys:
        problems.append(
            f"{n_whys} whys reached but only {len(rows)} prevention row(s) — "
            "a postmortem that fixes only the instance is the failure mode")

    for level, prevention, kind, status in rows:
        where = f"level {level}"
        # A prevention may legitimately quote the phrase while describing what
        # it rejects, so quoted spans do not count. Matching inside them made
        # this fail on the first real postmortem it was run against.
        unquoted = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d|`[^`]*`', " ", prevention)
        if _REMEMBER_RE.search(unquoted):
            problems.append(
                f"{where}: prevention reads as an instruction "
                f"({prevention.strip()[:50]!r}) — mechanise it or mark it declined")
        s = status.strip().lower()
        if s not in VALID_STATUS:
            problems.append(
                f"{where}: status {status.strip()!r} is not one of "
                f"{sorted(VALID_STATUS)}")
        if not prevention.strip():
            problems.append(f"{where}: prevention cell is empty")

    return problems


def _targets(argv: list[str]) -> list[Path]:
    if argv:
        return [Path(a) for a in argv]
    return [f for f in sorted(DIR.glob("*.md"))
            if f.name != "TEMPLATE.md" and f.name >= RULE_START]


def _main(argv: list[str]) -> int:
    failed = 0
    files = _targets(argv)
    for f in files:
        problems = check(f.read_text(), is_template=f.name == "TEMPLATE.md")
        if problems:
            failed += 1
            print(f"❌ {f.name}")
            for p in problems:
                print(f"   - {p}")
    if failed:
        print(f"\n{failed} of {len(files)} postmortem(s) incomplete. "
              f"See docs/postmortems/TEMPLATE.md.")
        return 1
    print(f"Postmortems: {len(files)} checked, all invest at every level reached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
