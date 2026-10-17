"""Tests for scan_state: self-healing scan windows, orphaned-run recovery, coverage gaps.

Each behaviour here is grounded in a real failure during the week of 2026-10-10:
  - Oct 12/13: scans did not fire; the next run's hardcoded "24h" window never
    covered the gap, so three posts (108/81/68 reactions) went unseen for days.
  - Oct 15: a turn launched six Apify runs then died before triage. The dataset
    ids lived only in conversation context, so the paid data was nearly orphaned.
  - Nothing detected either condition; a human had to ask.
"""

import json

import pytest

from scan_state import (
    ack_gap,
    choose_posted_limit,
    clear_run,
    coverage_gaps,
    is_gap_acked,
    list_acked_gaps,
    list_pending,
    read_watermark,
    record_run,
    write_watermark,
)


# --- self-healing window selection -------------------------------------------------

@pytest.mark.parametrize(
    "last,now,expected",
    [
        # fired on time -> cheapest window that covers it
        ("2026-10-16T09:00:00Z", "2026-10-17T09:05:00Z", "24h"),
        ("2026-10-17T06:00:00Z", "2026-10-17T09:00:00Z", "24h"),
        # missed a day (the Oct 12/13 case) -> widen, do not silently lose the gap
        ("2026-10-15T09:00:00Z", "2026-10-17T09:00:00Z", "week"),
        ("2026-10-11T09:00:00Z", "2026-10-17T09:00:00Z", "week"),
        # laptop shut for over a week -> month
        ("2026-10-01T09:00:00Z", "2026-10-17T09:00:00Z", "month"),
        # long dormancy
        ("2026-07-01T09:00:00Z", "2026-10-17T09:00:00Z", "3months"),
    ],
)
def test_window_widens_to_cover_the_actual_gap(last, now, expected):
    assert choose_posted_limit(last, now) == expected


def test_cron_jitter_does_not_widen_the_window():
    # A daily cron drifts: scheduler jitter plus "only fires when the REPL is
    # idle" means 9:07 can become 10:30. That is not an outage and must not
    # widen to "week", or the cost saving disappears on day one.
    assert choose_posted_limit("2026-10-16T09:07:00Z", "2026-10-17T10:30:00Z") == "24h"


def test_a_genuinely_skipped_day_does_widen():
    # The Oct 12/13 case: a cycle did not run at all, so the gap is ~2 days.
    assert choose_posted_limit("2026-10-15T09:00:00Z", "2026-10-17T09:07:00Z") == "week"


def test_never_scanned_defaults_to_week_not_month():
    # A new source should not trigger a huge first pull on a capped budget.
    assert choose_posted_limit(None, "2026-10-17T09:00:00Z") == "week"


def test_window_is_always_a_valid_actor_enum():
    allowed = {"any", "1h", "24h", "week", "month", "3months", "6months", "year"}
    for days in (0, 1, 2, 6, 7, 8, 29, 31, 200, 5000):
        last = f"2026-01-01T00:00:00Z"
        now = f"2026-01-01T00:00:00Z"
        assert choose_posted_limit(last, now) in allowed
    assert choose_posted_limit("2026-01-01T00:00:00Z", "2030-01-01T00:00:00Z") in allowed


def test_clock_skew_does_not_produce_a_negative_window(tmp_path):
    # last scan in the future (clock skew / timezone slip) must not crash or widen
    assert choose_posted_limit("2026-10-18T09:00:00Z", "2026-10-17T09:00:00Z") == "24h"


# --- watermarks ---------------------------------------------------------------------

def test_watermark_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    assert read_watermark("linkedin-keyword", path=p) is None
    write_watermark("linkedin-keyword", "2026-10-17T09:00:00Z", path=p)
    assert read_watermark("linkedin-keyword", path=p) == "2026-10-17T09:00:00Z"


def test_watermarks_are_per_source(tmp_path):
    p = tmp_path / "state.json"
    write_watermark("linkedin-keyword", "2026-10-17T09:00:00Z", path=p)
    write_watermark("linkedin-mentions", "2026-10-15T18:00:00Z", path=p)
    assert read_watermark("linkedin-keyword", path=p) == "2026-10-17T09:00:00Z"
    assert read_watermark("linkedin-mentions", path=p) == "2026-10-15T18:00:00Z"


def test_watermark_survives_a_corrupt_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not json")
    # must degrade to "never scanned" rather than crash the scan
    assert read_watermark("linkedin-keyword", path=p) is None
    write_watermark("linkedin-keyword", "2026-10-17T09:00:00Z", path=p)
    assert read_watermark("linkedin-keyword", path=p) == "2026-10-17T09:00:00Z"


# --- orphaned run recovery ----------------------------------------------------------

def test_pending_run_is_recoverable_after_the_turn_dies(tmp_path):
    p = tmp_path / "pending.json"
    record_run("ds123", actor="harvestapi/linkedin-post-search",
               label="kw-ries", launched_at="2026-10-17T09:00:00Z", path=p)
    pend = list_pending(path=p)
    assert len(pend) == 1
    assert pend[0]["dataset_id"] == "ds123"
    assert pend[0]["label"] == "kw-ries"


def test_clearing_a_run_removes_only_that_run(tmp_path):
    p = tmp_path / "pending.json"
    record_run("ds1", actor="a", label="one", launched_at="2026-10-17T09:00:00Z", path=p)
    record_run("ds2", actor="a", label="two", launched_at="2026-10-17T09:01:00Z", path=p)
    clear_run("ds1", path=p)
    assert [r["dataset_id"] for r in list_pending(path=p)] == ["ds2"]


def test_recording_the_same_dataset_twice_does_not_duplicate(tmp_path):
    p = tmp_path / "pending.json"
    for _ in range(3):
        record_run("ds1", actor="a", label="one", launched_at="2026-10-17T09:00:00Z", path=p)
    assert len(list_pending(path=p)) == 1


def test_clearing_an_unknown_dataset_is_a_noop(tmp_path):
    p = tmp_path / "pending.json"
    record_run("ds1", actor="a", label="one", launched_at="2026-10-17T09:00:00Z", path=p)
    clear_run("nope", path=p)
    assert len(list_pending(path=p)) == 1


# --- coverage gap detection ---------------------------------------------------------

def _touch(d, name):
    (d / name).write_text("[]")


def test_coverage_gaps_finds_the_day_a_source_never_ran(tmp_path):
    raw = tmp_path / "linkedin-raw"
    raw.mkdir()
    _touch(raw, "2026-10-12-kw-ries.json")
    # no mentions file on the 12th -> that is the Oct 12 hole
    _touch(raw, "2026-10-13-kw-ries.json")
    _touch(raw, "2026-10-13-mentions-24h.json")
    gaps = coverage_gaps(raw, "2026-10-12", "2026-10-13",
                         sources={"keyword": "kw-", "mentions": "mentions"})
    assert gaps == [("2026-10-12", ["mentions"])]


def test_coverage_gaps_clean_when_every_source_ran(tmp_path):
    raw = tmp_path / "linkedin-raw"
    raw.mkdir()
    _touch(raw, "2026-10-12-kw-ries.json")
    _touch(raw, "2026-10-12-mentions-24h.json")
    gaps = coverage_gaps(raw, "2026-10-12", "2026-10-12",
                         sources={"keyword": "kw-", "mentions": "mentions"})
    assert gaps == []


def test_coverage_gaps_ignores_catchup_and_audit_files(tmp_path):
    # a catch-up pull should not mask a genuine daily hole
    raw = tmp_path / "linkedin-raw"
    raw.mkdir()
    _touch(raw, "2026-10-12-catchup-kw-week.json")
    _touch(raw, "2026-10-12-audit-prod.json")
    gaps = coverage_gaps(raw, "2026-10-12", "2026-10-12",
                         sources={"keyword": "kw-", "mentions": "mentions"})
    assert gaps == [("2026-10-12", ["keyword", "mentions"])]


def test_coverage_gaps_matches_both_keyword_naming_conventions(tmp_path):
    # The daily keyword scan has written two filename shapes over time:
    # "keyword-24h.json" (through ~Oct 4) and "kw-ries.json" (after). A matcher
    # that knows only one invents gaps on the other's days.
    raw = tmp_path / "linkedin-raw"
    raw.mkdir()
    _touch(raw, "2026-10-03-keyword-24h.json")
    _touch(raw, "2026-10-03-mentions-24h.json")
    _touch(raw, "2026-10-12-kw-ries.json")
    _touch(raw, "2026-10-12-mentions-24h.json")
    sources = {"keyword": (("kw-", "keyword"), ("comments", "week")),
               "mentions": ("mentions", ())}
    assert coverage_gaps(raw, "2026-10-03", "2026-10-03", sources) == []
    assert coverage_gaps(raw, "2026-10-12", "2026-10-12", sources) == []


def test_comment_archive_files_do_not_count_as_keyword_coverage(tmp_path):
    # "keyword-week-comments.json" is the comment-archive job, which ships
    # nothing and runs Mon/Wed/Fri. It must not mask a missing daily scan.
    raw = tmp_path / "linkedin-raw"
    raw.mkdir()
    _touch(raw, "2026-10-13-keyword-week-comments.json")
    _touch(raw, "2026-10-13-kw-ries-comments.json")
    sources = {"keyword": (("kw-", "keyword"), ("comments", "week"))}
    assert coverage_gaps(raw, "2026-10-13", "2026-10-13", sources) == [
        ("2026-10-13", ["keyword"])
    ]


def test_coverage_gaps_handles_a_missing_directory(tmp_path):
    gaps = coverage_gaps(tmp_path / "nope", "2026-10-12", "2026-10-12",
                         sources={"keyword": "kw-"})
    assert gaps == [("2026-10-12", ["keyword"])]


# --- acknowledging backfilled gaps -------------------------------------------------
# Catch-up pulls are deliberately excluded from counting as coverage, so that a
# backfill cannot mask a genuine hole. The side effect, found on 2026-10-17 by
# running the tool: a gap that HAS been backfilled keeps reporting forever, and
# a report that accumulates permanent noise is one that stops being read.

def test_acked_gap_is_remembered(tmp_path):
    p = tmp_path / "acks.json"
    assert is_gap_acked("mentions", "2026-10-12", path=p) is False
    ack_gap("mentions", "2026-10-12", note="backfilled by week catch-up", path=p)
    assert is_gap_acked("mentions", "2026-10-12", path=p) is True


def test_ack_is_scoped_to_source_and_date(tmp_path):
    p = tmp_path / "acks.json"
    ack_gap("mentions", "2026-10-12", note="x", path=p)
    assert is_gap_acked("keyword", "2026-10-12", path=p) is False
    assert is_gap_acked("mentions", "2026-10-13", path=p) is False


def test_acking_twice_is_idempotent(tmp_path):
    p = tmp_path / "acks.json"
    for _ in range(3):
        ack_gap("mentions", "2026-10-12", note="x", path=p)
    assert len(list_acked_gaps(path=p)) == 1


def test_ack_survives_a_corrupt_file(tmp_path):
    p = tmp_path / "acks.json"
    p.write_text("{broken")
    assert is_gap_acked("mentions", "2026-10-12", path=p) is False
    ack_gap("mentions", "2026-10-12", note="x", path=p)
    assert is_gap_acked("mentions", "2026-10-12", path=p) is True


def test_ack_records_why_so_the_history_is_auditable(tmp_path):
    p = tmp_path / "acks.json"
    ack_gap("mentions", "2026-10-12", note="recovered 4 entries via week catch-up", path=p)
    rec = list_acked_gaps(path=p)[0]
    assert rec["source"] == "mentions"
    assert rec["date"] == "2026-10-12"
    assert "catch-up" in rec["note"]
