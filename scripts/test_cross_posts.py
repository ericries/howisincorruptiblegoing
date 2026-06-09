"""Tests for lib.cross_posts — source marker inference + state merge.

Run: uv run --with pytest pytest scripts/test_cross_posts.py -v
"""
import json
from pathlib import Path

import pytest

from lib.cross_posts import (
    infer_source_markers,
    merge_state,
)

# === Source marker inference ===

def test_no_source_urls_returns_empty():
    assert infer_source_markers({"source_url": None, "source_urls": None}) == {}


def test_linkedin_in_source_url():
    e = {"source_url": "https://www.linkedin.com/posts/eries_abc", "source_urls": None}
    assert infer_source_markers(e) == {"linkedin": "source"}


def test_twitter_alias_to_x():
    e = {"source_url": "https://twitter.com/foo/status/123"}
    assert infer_source_markers(e) == {"x": "source"}


def test_x_com_marks_x():
    e = {"source_url": "https://x.com/foo/status/123"}
    assert infer_source_markers(e) == {"x": "source"}


def test_bsky_app_marks_bluesky():
    e = {"source_url": "https://bsky.app/profile/foo/post/123"}
    assert infer_source_markers(e) == {"bluesky": "source"}


def test_secondary_source_urls_considered():
    e = {
        "source_url": "https://fastcompany.com/x",
        "source_urls": [{"url": "https://www.linkedin.com/foo"}],
    }
    assert infer_source_markers(e) == {"linkedin": "source"}


def test_multiple_platforms_all_marked():
    e = {
        "source_url": "https://www.linkedin.com/x",
        "source_urls": [{"url": "https://x.com/y"}],
    }
    assert infer_source_markers(e) == {"linkedin": "source", "x": "source"}


def test_non_platform_url_no_marker():
    assert infer_source_markers({"source_url": "https://fastcompany.com/x"}) == {}


# === Merge state ===

def test_merge_into_empty_state():
    out = merge_state({}, {"e1": {"linkedin": "source"}})
    assert out == {
        "e1": {
            "linkedin": "source",
            "x": None,
            "bluesky": None,
            "instagram": None,
        }
    }


def test_scheduled_timestamp_preserved_over_source():
    existing = {"e1": {"bluesky": "2026-06-11T09:00:00-07:00"}}
    new = {"e1": {"bluesky": "source"}}
    assert merge_state(existing, new)["e1"]["bluesky"] == "2026-06-11T09:00:00-07:00"


def test_source_marker_fills_null():
    existing = {"e1": {"bluesky": None}}
    new = {"e1": {"bluesky": "source"}}
    assert merge_state(existing, new)["e1"]["bluesky"] == "source"
