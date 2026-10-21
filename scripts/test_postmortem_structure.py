"""Every postmortem must name a prevention at each level it reached.

Eric, 2026-10-21: "do these root cause analyses routinely, always make
proportional investments in prevention at each level."

The failure this guards is the one the 2026-10-21 postmortem diagnosed: an
analysis that reaches depth five and then ships only the level-one instance fix.
Writing the whys is the easy half; the prevention table is where the investment
is either made or quietly skipped, so it is the part that gets checked.
"""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "postmortem_lint", Path(__file__).resolve().parent / "postmortem-lint.py")
pl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pl)

DIR = Path(__file__).resolve().parent.parent / "docs" / "postmortems"

GOOD = """# Something broke

## Five whys

**1. Why?** a
**2. Why?** b

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | fixed the entry | fix | shipped |
| 2 — the local condition | lint check | check | shipped |
"""


def test_a_complete_postmortem_passes():
    assert pl.check(GOOD) == []


def test_missing_prevention_table_is_reported():
    text = GOOD.split("## Prevention")[0]
    assert any("prevention" in p.lower() for p in pl.check(text))


def test_fewer_prevention_rows_than_whys_is_reported():
    text = GOOD.replace("| 2 — the local condition | lint check | check | shipped |\n", "")
    problems = pl.check(text)
    assert any("2 whys" in p and "1" in p for p in problems), problems


def test_a_remember_to_prevention_is_rejected():
    # "remember to" is the instance fix wearing a hat.
    text = GOOD.replace("lint check", "remember to grep before writing")
    assert any("remember" in p.lower() for p in pl.check(text))


def test_a_quoted_mention_of_the_phrase_is_not_a_hit():
    # A prevention may legitimately describe rejecting the phrase, as the
    # 2026-10-21 postmortem's level-five row does. Matching inside quotes made
    # the check fail on the first real file it ran against.
    text = GOOD.replace("lint check", 'rejects a prevention reading "remember to"')
    assert pl.check(text) == []


def test_an_unquoted_instruction_is_still_a_hit():
    text = GOOD.replace("lint check", "remember to grep first")
    assert any("instruction" in p for p in pl.check(text))


def test_an_unknown_status_is_rejected():
    text = GOOD.replace("| check | shipped |", "| check | maybe |")
    assert any("status" in p.lower() for p in pl.check(text))


def test_declined_is_an_acceptable_status():
    text = GOOD.replace("| check | shipped |", "| check | declined |")
    assert pl.check(text) == []


def test_the_template_itself_is_skipped():
    assert pl.check((DIR / "TEMPLATE.md").read_text(), is_template=True) == []


# --- the real corpus -----------------------------------------------------------

def test_todays_postmortems_are_well_formed():
    # Scoped to postmortems written on or after 2026-10-21, when the rule began.
    # Retrofitting the back catalogue is a separate job; failing on it would just
    # train me to skip the check.
    stale = []
    for f in sorted(DIR.glob("2026-1*.md")):
        if f.name == "TEMPLATE.md" or f.name < "2026-10-21":
            continue
        problems = pl.check(f.read_text())
        if problems:
            stale.append((f.name, problems))
    assert stale == [], stale
