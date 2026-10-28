"""Does a feed pull reach back far enough to meet the previous pull?

`scan_catchup` answers "did the job run". That is not the same question. On
2026-10-24 and again on 2026-10-27 the comment-archive job ran exactly on
schedule, wrote its watermark, and still never saw a day of Eric's posts —
because the item cap truncated the pull before it reached back to where the
previous run stopped. Catch-up reported "nothing overdue" both times, correctly.

The hole was found by hand, by reading two date ranges off a table and comparing
them, which is precisely the kind of check that works until the day nobody does
it. These tests pin the comparison so a script does it instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from feed_coverage import (
    find_holes,
    is_starved,
    post_dates,
    run_span,
)

RAW = Path(__file__).resolve().parent.parent / "data" / "archive" / "linkedin-raw"


def post(date: str, **kw):
    """A post item: harvestapi marks posts by carrying an `author`."""
    return {"author": {"name": "Eric Ries"}, "postedAt": {"date": f"{date}T12:00:00.000Z"}, **kw}


def comment(**kw):
    """A comment item: no `author` key, dated by createdAt."""
    return {"commentary": "nice", "createdAt": 1793210750384, **kw}


# --- reading post dates out of a raw dataset ---------------------------------------

def test_post_dates_ignores_comment_items():
    items = [comment(), post("2026-10-28"), comment(), post("2026-10-27")]
    assert post_dates(items) == ["2026-10-27", "2026-10-28"]


def test_post_dates_accepts_plain_string_posted_at():
    """Older archive files store postedAt as a bare ISO string."""
    items = [{"author": {"name": "x"}, "postedAt": "2026-10-20T09:00:00.000Z"}]
    assert post_dates(items) == ["2026-10-20"]


def test_post_dates_skips_posts_with_no_usable_date():
    items = [post("2026-10-28"), {"author": {"name": "x"}, "postedAt": None}]
    assert post_dates(items) == ["2026-10-28"]


def test_post_dates_empty_for_comment_only_dataset():
    assert post_dates([comment(), comment()]) == []


# --- the span a run actually covered ------------------------------------------------

def test_run_span_is_oldest_to_newest_post():
    items = [post("2026-10-28"), post("2026-10-25"), post("2026-10-26")]
    assert run_span(items) == ("2026-10-25", "2026-10-28")


def test_run_span_is_none_when_no_posts():
    assert run_span([comment()]) is None


# --- holes between consecutive runs -------------------------------------------------

def test_no_hole_when_runs_overlap():
    runs = [
        {"file": "a", "span": ("2026-10-21", "2026-10-23")},
        {"file": "b", "span": ("2026-10-22", "2026-10-26")},
    ]
    assert find_holes(runs) == []


def test_no_hole_when_runs_are_exactly_adjacent():
    """B reaching back to A's newest day leaves nothing uncovered."""
    runs = [
        {"file": "a", "span": ("2026-10-21", "2026-10-23")},
        {"file": "b", "span": ("2026-10-23", "2026-10-26")},
    ]
    assert find_holes(runs) == []


def test_no_hole_when_b_starts_the_day_after_a_ends():
    """A covered through the 23rd, B starts on the 24th — contiguous."""
    runs = [
        {"file": "a", "span": ("2026-10-21", "2026-10-23")},
        {"file": "b", "span": ("2026-10-24", "2026-10-26")},
    ]
    assert find_holes(runs) == []


def test_one_day_hole_is_reported():
    """The 2026-10-27 shape: A stops on the 26th, B starts on the 28th."""
    runs = [
        {"file": "a", "span": ("2026-10-25", "2026-10-26")},
        {"file": "b", "span": ("2026-10-28", "2026-10-28")},
    ]
    assert find_holes(runs) == [
        {"after": "a", "before": "b", "dates": ["2026-10-27"]}
    ]


def test_multi_day_hole_lists_every_date():
    runs = [
        {"file": "a", "span": ("2026-10-18", "2026-10-20")},
        {"file": "b", "span": ("2026-10-25", "2026-10-26")},
    ]
    assert find_holes(runs)[0]["dates"] == [
        "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24",
    ]


def test_runs_with_no_posts_are_skipped_not_crashed():
    runs = [
        {"file": "a", "span": ("2026-10-25", "2026-10-26")},
        {"file": "empty", "span": None},
        {"file": "b", "span": ("2026-10-28", "2026-10-28")},
    ]
    # The empty run neither covers nor breaks anything; the hole is still a..b.
    assert find_holes(runs) == [
        {"after": "a", "before": "b", "dates": ["2026-10-27"]}
    ]


def test_single_run_has_no_holes():
    assert find_holes([{"file": "a", "span": ("2026-10-25", "2026-10-26")}]) == []


# --- starvation: the cap binding, and what it cost ----------------------------------

def test_starved_when_at_cap_and_short_of_post_quota():
    """39 items against a cap of 40, carrying 6 of a requested 30 posts."""
    assert is_starved(n_items=39, n_posts=6, cap=40, max_posts=30) is True


def test_not_starved_when_well_under_cap():
    assert is_starved(n_items=72, n_posts=30, cap=400, max_posts=30) is False


def test_not_starved_when_at_cap_but_post_quota_met():
    """The cap bound, but only after every requested post was already in."""
    assert is_starved(n_items=40, n_posts=30, cap=40, max_posts=30) is False


def test_not_starved_when_feed_simply_had_fewer_posts():
    """Under the cap and short of quota means Eric posted less, not truncation."""
    assert is_starved(n_items=12, n_posts=4, cap=40, max_posts=30) is False


# --- regression against the real datasets -------------------------------------------

@pytest.mark.skipif(not RAW.exists(), reason="raw archive is gitignored/local")
def test_real_author_runs_show_the_2026_10_27_hole():
    """The failure this module exists for, read off the actual files."""
    pairs = []
    for name in ("2026-10-26-comments-author.json", "2026-10-28-comments-author.json"):
        f = RAW / name
        if not f.exists():
            pytest.skip(f"{name} not present")
        pairs.append({"file": name, "span": run_span(json.loads(f.read_text()))})
    holes = find_holes(pairs)
    assert holes, "the 10-26 -> 10-28 author pair must report a hole"
    assert "2026-10-27" in holes[0]["dates"]


@pytest.mark.skipif(not RAW.exists(), reason="raw archive is gitignored/local")
def test_real_precap_run_was_not_starved():
    """2026-10-14 returned 130 items: 30 posts and 100 comments.

    maxPosts was honoured exactly. The CRONS.md note that read this as
    "maxPosts is NOT honoured (30 was passed, 130 returned)" was counting
    comments as posts, and that misreading is what put the total-item cap on
    the call in the first place.
    """
    f = RAW / "2026-10-14-eries-author-feed.json"
    if not f.exists():
        pytest.skip("pre-cap dataset not present")
    items = json.loads(f.read_text())
    n_posts = len(post_dates(items))
    assert n_posts == 30, f"maxPosts:30 should have been honoured, got {n_posts}"
    assert len(items) == 130


# --- the prompt and the detector cannot drift apart ---------------------------------

CRONS = Path(__file__).resolve().parent.parent / "docs" / "CRONS.md"


def test_lane_request_matches_the_caps_in_crons_md():
    """The starvation alarm is only armed if it knows the real cap.

    This is the level-5 fix from docs/postmortems/2026-10-28. The 40-item cap
    did its damage because it existed only as prose in a cron prompt — nothing
    in the repo could read it, so nothing could check what it was doing. Now the
    cap lives in LANE_REQUEST too, and that creates a new way to fail silently:
    lower the cap in CRONS.md, forget the constant, and `is_starved` goes quiet
    for exactly the runs it should be shouting about.

    So the two are pinned to each other. A future cap change either updates both
    or fails here.
    """
    from feed_coverage import LANE_REQUEST

    text = CRONS.read_text()
    # Anchor on the section HEADING, not the prompt's opening phrase: that phrase
    # also appears in the watchdog's job list further up, and splitting there
    # scoped the search to the wrong section entirely.
    heading = re.search(r"^## \d+\. LinkedIn comment archive.*$", text, re.M)
    assert heading, "comment-archive section heading not found in CRONS.md"
    body = text[heading.end():].split("\n## ", 1)[0]

    caps = {int(m) for m in re.findall(r'callOptions \{"maxItems": (\d+)\}', body)}
    posts = {int(m) for m in re.findall(r'"maxPosts": (\d+)', body)}
    assert caps, "no maxItems found in the comment-archive prompt"
    assert posts, "no maxPosts found in the comment-archive prompt"

    for lane, req in LANE_REQUEST.items():
        assert req["cap"] in caps, (
            f"LANE_REQUEST[{lane!r}]['cap'] == {req['cap']} but CRONS.md asks for "
            f"{sorted(caps)} — the starvation check would use the wrong threshold")
        assert req["max_posts"] in posts, (
            f"LANE_REQUEST[{lane!r}]['max_posts'] == {req['max_posts']} but CRONS.md "
            f"asks for {sorted(posts)}")


def test_cap_is_a_backstop_not_an_operating_constraint():
    """A cap below the post quota's plausible item count re-creates starvation.

    30 posts averaged 3.3 comments each across the pre-cap archive, and 5.5 on a
    busy day. A cap must clear max_posts * 5 or it will bind in normal operation
    rather than acting as the runaway backstop it is meant to be.
    """
    from feed_coverage import LANE_REQUEST

    for lane, req in LANE_REQUEST.items():
        floor = req["max_posts"] * 5
        assert req["cap"] >= floor, (
            f"{lane}: cap {req['cap']} is below {floor} (max_posts x 5 observed "
            f"comments/post) — it will truncate normal pulls, not just runaways")


# --- a later pull can close an earlier hole -----------------------------------------

def test_a_wide_recovery_pull_closes_an_earlier_hole():
    """Found by using the tool: after re-pulling 10-27 it still reported the hole.

    The pairwise comparison asked "did run N+1 reach back to run N", which is
    the wrong question once an out-of-band recovery pull exists. The right
    question is whether ANY run covered the date. A hole that has been filled
    must stop being reported, or the signal trains you to ignore it.
    """
    runs = [
        {"file": "a", "span": ("2026-10-25", "2026-10-26")},
        {"file": "b", "span": ("2026-10-28", "2026-10-28")},
        {"file": "recovery", "span": ("2026-10-22", "2026-10-28")},
    ]
    assert find_holes(runs) == []


def test_hole_survives_a_recovery_that_does_not_reach_it():
    runs = [
        {"file": "a", "span": ("2026-10-20", "2026-10-21")},
        {"file": "b", "span": ("2026-10-28", "2026-10-28")},
        {"file": "recovery", "span": ("2026-10-25", "2026-10-28")},
    ]
    holes = find_holes(runs)
    assert holes and holes[0]["dates"] == [
        "2026-10-22", "2026-10-23", "2026-10-24",
    ]


def test_recovery_files_are_part_of_their_lane(tmp_path):
    """A recovery pull is a first-class member of the lane, not a stray file."""
    from feed_coverage import lane_runs

    (tmp_path / "2026-10-26-comments-author.json").write_text(json.dumps(
        [post("2026-10-26")]))
    (tmp_path / "2026-10-28-recovery-author.json").write_text(json.dumps(
        [post("2026-10-22"), post("2026-10-28")]))
    (tmp_path / "2026-10-28-keyword-bare.json").write_text(json.dumps(
        [post("2026-10-28")]))

    files = [r["file"] for r in lane_runs("author", tmp_path)]
    assert files == ["2026-10-26-comments-author.json",
                     "2026-10-28-recovery-author.json"]
