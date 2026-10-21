"""Tests for reading cron prompts out of docs/CRONS.md.

Why this exists. Until 2026-10-21 the flow ran the wrong way: the watchdog
carried each job's LIVE prompt forward on every roll, and CRONS.md was supposed
to be re-synced afterwards by hand. It never kept up — on 2026-10-21 all seven
sections had drifted, and an earlier commit message claimed a CRONS.md edit that
had silently failed. Worse, a lesson learned during a scan lived only in an
in-memory cron, so it died with the session.

Flipping it fixes both: the watchdog reads the prompt from CRONS.md and passes it
to CronCreate verbatim, and any lesson a scan learns has to be written to
CRONS.md to survive — which is version control, which is the point.
"""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "cron_prompt", Path(__file__).resolve().parent / "cron-prompt.py")
cp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cp)

DOC = Path(__file__).resolve().parent.parent / "docs" / "CRONS.md"


# --- extraction -----------------------------------------------------------------

def test_every_scheduled_job_has_an_extractable_prompt():
    for job in cp.JOBS:
        prompt = cp.prompt_for(job)
        assert prompt.strip(), job
        assert len(prompt) > 200, f"{job} prompt suspiciously short"


def test_the_prompt_excludes_the_fence_markers():
    p = cp.prompt_for("watchdog")
    assert not p.lstrip().startswith("```")
    assert "```" not in p


def test_the_prompt_is_the_section_body_not_the_heading():
    p = cp.prompt_for("morning-scan")
    assert not p.lstrip().startswith("##")
    assert "Morning content scan" in p


def test_sections_do_not_bleed_into_each_other():
    watchdog = cp.prompt_for("watchdog")
    assert "Goodreads review scan. Follow" not in watchdog
    goodreads = cp.prompt_for("goodreads")
    assert "Cron watchdog. Run CronList" not in goodreads


def test_an_unknown_job_raises_rather_than_returning_empty():
    with pytest.raises(KeyError):
        cp.prompt_for("no-such-job")


# --- the table and the sections agree --------------------------------------------

def test_cron_expressions_match_the_schedule_table():
    table = cp.schedule_table()
    for job, spec in cp.JOBS.items():
        assert table[spec["heading"]] == spec["cron"], job


def test_all_seven_jobs_are_present():
    assert len(cp.JOBS) == 7


def test_each_prompt_names_its_own_job():
    # A copy-paste that lands the wrong prompt under a heading is the failure
    # this catches — it would otherwise quietly reschedule the wrong work.
    for job, spec in cp.JOBS.items():
        assert spec["signature"] in cp.prompt_for(job), job


# --- the doc still parses at all --------------------------------------------------

def test_the_file_has_exactly_one_fenced_block_per_job_section():
    text = DOC.read_text()
    for job, spec in cp.JOBS.items():
        start = text.index(spec["heading"])
        nxt = text.find("\n## ", start + 1)
        body = text[start: nxt if nxt != -1 else len(text)]
        assert body.count("```") == 2, f"{job} section must hold exactly one fenced block"
