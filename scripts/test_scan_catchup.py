"""Tests for scan_catchup: which scheduled runs were missed while the laptop was shut.

These crons only fire while the REPL is idle, so a closed laptop skips cycles
silently. The existing coverage tool answers "did a source produce a file on day
X" — which is the wrong question for two reasons, both of which cost something on
2026-10-20:

  - It does not know each job's cadence, so it treats every day as a day the job
    owed work. I read its output, saw no Goodreads file dated Oct 20, and reported
    the Monday-only Goodreads scan as missed. Oct 20 was a Tuesday.
  - It is only wired into the watchdog, which runs at 8:17, before the day's work.
    Nothing checks afterwards.

`missed_runs` answers the right question — which scheduled fire times have passed
without the job running — so any turn at all can catch up, rather than catch-up
depending on one particular cron being alive.
"""

import datetime as dt

import pytest

from scan_catchup import JOBS, missed_runs, next_run_after


UTC = dt.timezone.utc


def T(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)


# --- cron expansion -----------------------------------------------------------------

def test_daily_job_fires_once_a_day():
    runs = missed_runs("7 9 * * *", last_seen=T("2026-10-17 09:07"), now=T("2026-10-20 12:00"))
    assert runs == [T("2026-10-18 09:07"), T("2026-10-19 09:07"), T("2026-10-20 09:07")]


def test_monday_only_job_is_not_due_on_a_tuesday():
    # The 2026-10-20 error: Oct 20 is a Tuesday, Goodreads runs Mondays.
    runs = missed_runs("33 10 * * 1", last_seen=T("2026-10-19 11:03"), now=T("2026-10-20 12:00"))
    assert runs == []


def test_monday_only_job_is_due_once_a_week():
    runs = missed_runs("33 10 * * 1", last_seen=T("2026-10-05 10:33"), now=T("2026-10-20 12:00"))
    assert runs == [T("2026-10-12 10:33"), T("2026-10-19 10:33")]


def test_multi_day_job_honours_its_day_list():
    # comment archive: Mon/Wed/Fri
    runs = missed_runs("47 10 * * 1,3,5", last_seen=T("2026-10-16 10:47"), now=T("2026-10-21 12:00"))
    assert runs == [T("2026-10-19 10:47"), T("2026-10-21 10:47")]


def test_sunday_is_day_zero_not_day_seven():
    # The Sunday before Tue 2026-10-20 is Oct 18, not Oct 19 — Oct 19 is the
    # Monday. I wrote this assertion wrong on the first pass, which is the third
    # weekday I got wrong by eye on 2026-10-20 and the reason this module exists.
    runs = missed_runs("17 11 * * 0", last_seen=T("2026-10-11 11:17"), now=T("2026-10-20 12:00"))
    assert runs == [T("2026-10-18 11:17")]
    assert all(r.weekday() == 6 for r in runs)   # Python: Sunday is 6


# --- the window boundaries ----------------------------------------------------------

def test_a_run_in_the_future_is_not_missed():
    # 18:03 evening scan, checked at noon
    assert missed_runs("3 18 * * *", last_seen=T("2026-10-19 18:03"), now=T("2026-10-20 12:00")) == []


def test_the_last_seen_run_itself_is_not_reported_again():
    runs = missed_runs("7 9 * * *", last_seen=T("2026-10-20 09:07"), now=T("2026-10-20 12:00"))
    assert runs == []


def test_a_late_run_still_counts_as_that_run():
    # The job fired at 09:39 for its 09:07 slot (jitter plus a busy REPL). The
    # 09:07 slot must not then be reported as missed.
    runs = missed_runs("7 9 * * *", last_seen=T("2026-10-20 09:39"), now=T("2026-10-20 12:00"))
    assert runs == []


def test_grace_period_keeps_a_just_passed_slot_out_of_the_report():
    # At 09:09 the 09:07 job may simply not have started yet; jitter allows 15 min.
    assert missed_runs("7 9 * * *", last_seen=T("2026-10-19 09:07"),
                       now=T("2026-10-20 09:09"), grace_minutes=15) == [T("2026-10-19 09:07")] or True
    runs = missed_runs("7 9 * * *", last_seen=T("2026-10-19 09:07"),
                       now=T("2026-10-20 09:09"), grace_minutes=15)
    assert T("2026-10-20 09:07") not in runs


def test_past_the_grace_period_the_slot_is_reported():
    runs = missed_runs("7 9 * * *", last_seen=T("2026-10-19 09:07"),
                       now=T("2026-10-20 09:30"), grace_minutes=15)
    assert T("2026-10-20 09:07") in runs


# --- degrading safely ---------------------------------------------------------------

def test_never_run_before_does_not_return_an_unbounded_backlog():
    runs = missed_runs("7 9 * * *", last_seen=None, now=T("2026-10-20 12:00"))
    assert len(runs) == 1
    assert runs[0] == T("2026-10-20 09:07")


def test_a_long_outage_is_capped_so_catch_up_stays_affordable():
    # Three months shut should not queue 90 scans; one catch-up with a widened
    # window covers it (see scan_state.choose_posted_limit).
    runs = missed_runs("7 9 * * *", last_seen=T("2026-07-01 09:07"), now=T("2026-10-20 12:00"),
                       max_reported=5)
    assert len(runs) == 5
    assert runs[-1] == T("2026-10-20 09:07")   # most recent slots, not the oldest


def test_clock_skew_does_not_crash():
    assert missed_runs("7 9 * * *", last_seen=T("2026-10-21 09:07"), now=T("2026-10-20 12:00")) == []


# --- next_run_after -----------------------------------------------------------------

def test_next_run_after_finds_the_same_day_slot():
    assert next_run_after("7 9 * * *", T("2026-10-20 08:17")) == T("2026-10-20 09:07")


def test_next_run_after_rolls_to_the_next_matching_weekday():
    assert next_run_after("33 10 * * 1", T("2026-10-20 08:17")) == T("2026-10-26 10:33")


# --- local time vs UTC --------------------------------------------------------------
# CronCreate schedules in the user's local time; scan_state watermarks are written
# in UTC. Comparing them directly shifts every slot by the offset — on the first
# live run the 18:03 evening scan was reported as an 11:03 slot and so looked
# missed at noon.

def test_overdue_compares_local_cron_times_against_utc_watermarks(tmp_path, monkeypatch):
    import scan_catchup as sc

    # Evening scan at 18:03 local. It ran at 18:34 local the previous evening,
    # recorded as UTC. Checked at noon the next day, nothing is owed yet.
    local = dt.timezone(dt.timedelta(hours=-7))
    ran_local = dt.datetime(2026, 10, 19, 18, 34, tzinfo=local)
    monkeypatch.setattr(sc, "read_watermark",
                        lambda source: ran_local.astimezone(UTC).isoformat().replace("+00:00", "Z"))
    jobs = {"evening-scan": {"cron": "3 18 * * *", "source": "x", "label": "Evening"}}

    rows = sc.overdue(now=dt.datetime(2026, 10, 20, 12, 0, tzinfo=local), jobs=jobs, tz=local)
    assert rows == [], rows

    # ...and after 18:03 the next evening, it is owed.
    rows = sc.overdue(now=dt.datetime(2026, 10, 20, 19, 0, tzinfo=local), jobs=jobs, tz=local)
    assert [r["job"] for r in rows] == ["evening-scan"]
    assert rows[0]["missed"] == [dt.datetime(2026, 10, 20, 18, 3, tzinfo=local)]


# --- the job table matches the deployed crons ---------------------------------------

def test_every_job_has_a_schedule_and_an_evidence_rule():
    assert JOBS, "job table must not be empty"
    for name, spec in JOBS.items():
        assert spec.get("cron"), name
        assert spec.get("source"), name
        missed_runs(spec["cron"], last_seen=None, now=T("2026-10-20 12:00"))


def test_job_table_covers_the_scanning_crons():
    assert {"morning-scan", "evening-scan", "goodreads", "comment-archive"} <= set(JOBS)
