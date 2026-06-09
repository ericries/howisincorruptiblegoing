"""Tests for backfill_cross_posts.run_backfill."""
import json
from pathlib import Path

import pytest

from backfill_cross_posts import run_backfill


def _write_entry(dir_path: Path, entry_id: str, **fields) -> None:
    payload = {"id": entry_id, **fields}
    (dir_path / f"{entry_id}.json").write_text(json.dumps(payload))


def test_backfill_writes_source_markers(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    _write_entry(entries_dir, "e1", source_url="https://www.linkedin.com/foo")
    state_path = tmp_path / "state.json"

    run_backfill(str(entries_dir), str(state_path))

    state = json.loads(state_path.read_text())
    assert state["e1"]["linkedin"] == "source"
    assert state["e1"]["x"] is None
    assert state["e1"]["bluesky"] is None
    assert state["e1"]["instagram"] is None


def test_backfill_creates_state_if_missing(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    _write_entry(entries_dir, "e1", source_url="https://x.com/foo/status/1")
    state_path = tmp_path / "state.json"
    assert not state_path.exists()

    run_backfill(str(entries_dir), str(state_path))

    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["e1"]["x"] == "source"


def test_backfill_idempotent_preserves_schedule(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    _write_entry(entries_dir, "e1", source_url="https://www.linkedin.com/foo")
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "e1": {
            "bluesky": "2026-06-11T09:00:00-07:00",
            "linkedin": "source",
        }
    }))

    run_backfill(str(entries_dir), str(state_path))

    state = json.loads(state_path.read_text())
    assert state["e1"]["bluesky"] == "2026-06-11T09:00:00-07:00"
    assert state["e1"]["linkedin"] == "source"


def test_backfill_skips_entries_without_platform_urls(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    _write_entry(entries_dir, "e1", source_url="https://fastcompany.com/article")
    state_path = tmp_path / "state.json"

    run_backfill(str(entries_dir), str(state_path))

    state = json.loads(state_path.read_text())
    # entry walked but no platform-source markers found → entry not added
    # (no source markers AND no schedule means nothing to persist for it)
    assert "e1" not in state


def test_backfill_handles_multiple_entries(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    _write_entry(entries_dir, "e1", source_url="https://www.linkedin.com/a")
    _write_entry(entries_dir, "e2", source_url="https://x.com/b/status/1")
    _write_entry(
        entries_dir,
        "e3",
        source_url="https://bsky.app/profile/c/post/1",
        source_urls=[{"url": "https://www.linkedin.com/d"}],
    )
    state_path = tmp_path / "state.json"

    run_backfill(str(entries_dir), str(state_path))

    state = json.loads(state_path.read_text())
    assert state["e1"]["linkedin"] == "source"
    assert state["e2"]["x"] == "source"
    assert state["e3"]["bluesky"] == "source"
    assert state["e3"]["linkedin"] == "source"
