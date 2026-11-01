"""The roll log: what the repo handed over, and whether the crons match it.

The watchdog's whole premise is that docs/CRONS.md outlives the session. Three
times — 2026-10-25, 2026-10-26 and 2026-11-01 — the file was found BEHIND the
live crons, because a roll enriched a prompt in flight and the addition was
never written back. The repair each time was a commit titled "write back the
lessons the roll carried forward". That is the instance fix, performed three
times, and no mechanism was ever built.

Nothing can read a live cron's full text back (CronList truncates to a
preview), so a true live-vs-file diff is impossible. What IS possible is to
make the handover leave a trace: the only sanctioned way to obtain a prompt now
also records its hash, and the watchdog reports a token per job. A roll whose
rolled byte count differs from its token is an enrichment that has not been
written back, and the next run can see it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cron_roll as cr  # noqa: E402


def test_digest_is_stable_and_counts_bytes():
    d1 = cr.digest("hello")
    d2 = cr.digest("hello")
    assert d1 == d2
    assert d1["bytes"] == 5
    assert len(d1["sha12"]) == 12


def test_digest_counts_bytes_not_characters():
    """`wc -c` reports bytes; mixing the two made the size diff lie on 11-01."""
    assert cr.digest("sans—dash")["bytes"] == len("sans—dash".encode())
    assert cr.digest("sans—dash")["bytes"] != len("sans—dash")


def test_record_then_check_reports_in_sync(tmp_path):
    log = tmp_path / "roll-log.json"
    cr.record("evening-scan", "the prompt text", "2026-11-01T18:00:00Z", path=log)
    rows = cr.check({"evening-scan": "the prompt text"}, path=log)
    assert rows["evening-scan"]["status"] == "in-sync"


def test_check_flags_a_section_edited_since_its_last_roll(tmp_path):
    """The live cron is now BEHIND the repo — the other drift direction."""
    log = tmp_path / "roll-log.json"
    cr.record("evening-scan", "old text", "2026-11-01T18:00:00Z", path=log)
    rows = cr.check({"evening-scan": "old text plus a new lesson"}, path=log)
    assert rows["evening-scan"]["status"] == "file-ahead"


def test_check_flags_a_job_never_rolled(tmp_path):
    log = tmp_path / "roll-log.json"
    rows = cr.check({"sidebar": "whatever"}, path=log)
    assert rows["sidebar"]["status"] == "never-rolled"


def test_record_keeps_the_previous_roll_as_history(tmp_path):
    log = tmp_path / "roll-log.json"
    cr.record("sidebar", "v1", "2026-10-31T19:00:00Z", path=log)
    cr.record("sidebar", "v2", "2026-11-01T19:00:00Z", path=log)
    data = json.loads(log.read_text())
    assert len(data["sidebar"]) == 2
    assert data["sidebar"][-1]["rolled_at"] == "2026-11-01T19:00:00Z"
    assert data["sidebar"][-1]["sha12"] == cr.digest("v2")["sha12"]


def test_history_is_bounded_so_the_log_does_not_grow_without_end(tmp_path):
    log = tmp_path / "roll-log.json"
    for i in range(cr.KEEP_ROLLS + 5):
        cr.record("sidebar", f"v{i}", f"2026-11-{i+1:02d}T19:00:00Z", path=log)
    data = json.loads(log.read_text())
    assert len(data["sidebar"]) == cr.KEEP_ROLLS


def test_rolled_bytes_matching_the_token_is_accepted(tmp_path):
    log = tmp_path / "roll-log.json"
    text = "the prompt"
    cr.record("sidebar", text, "2026-11-01T19:00:00Z", path=log)
    assert cr.verify_rolled("sidebar", len(text.encode()), path=log) == "ok"


def test_rolled_bytes_differing_from_the_token_is_an_unwritten_enrichment(tmp_path):
    """The 10-25, 10-26 and 11-01 failure, made visible at the moment it happens."""
    log = tmp_path / "roll-log.json"
    cr.record("evening-scan", "the prompt", "2026-11-01T19:00:00Z", path=log)
    verdict = cr.verify_rolled("evening-scan", 99999, path=log)
    assert verdict.startswith("ENRICHED")
    assert "patch docs/CRONS.md" in verdict


def test_verify_rolled_on_an_unrolled_job_says_so(tmp_path):
    log = tmp_path / "roll-log.json"
    assert cr.verify_rolled("sidebar", 10, path=log).startswith("never-rolled")
