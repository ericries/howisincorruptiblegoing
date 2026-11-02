"""Applying 253 rewrites from subagents, without taking their word for it.

The risk is not that a rewrite is clumsy — I can read those. It is that a
rewrite is fluent and wrong: a job title supplied, a number rounded, an id
quietly dropped from the batch. Each of those is invisible in a 253-file diff,
so the applier refuses rather than reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rewrite_apply as ra  # noqa: E402


def _entry(tmp_path, eid, **kw):
    d = {"id": eid, "date": "2026-06-01", "type": "review",
         "summary": "Old summary about Microsoft.", "blockquote": "A quote.",
         "title": "A title", "type_metadata": {}}
    d.update(kw)
    p = tmp_path / f"{eid}.json"
    p.write_text(json.dumps(d, indent=2) + "\n")
    return p


def test_a_clean_rewrite_is_accepted(tmp_path):
    _entry(tmp_path, "e1")
    v = ra.verdict_for("e1", "Microsoft is the subject of the piece.", entries_dir=tmp_path)
    assert v.ok, v.problems


def test_a_rewrite_introducing_an_unsourced_name_is_refused(tmp_path):
    _entry(tmp_path, "e1")
    v = ra.verdict_for("e1", "Salesforce is the subject.", entries_dir=tmp_path)
    assert not v.ok
    assert any("Salesforce" in p for p in v.problems)


def test_a_rewrite_with_a_relative_time_word_is_refused(tmp_path):
    _entry(tmp_path, "e1")
    v = ra.verdict_for("e1", "Microsoft announced an upcoming change.", entries_dir=tmp_path)
    assert not v.ok
    assert any("relative-time" in p for p in v.problems)


def test_a_rewrite_that_restates_the_blockquote_is_refused(tmp_path):
    _entry(tmp_path, "e1", blockquote="Missions die from unprotected structures every time.")
    v = ra.verdict_for("e1", "He argued missions die from unprotected structures every time.",
                       entries_dir=tmp_path)
    assert not v.ok
    assert any("echoes-blockquote" in p for p in v.problems)


def test_an_unchanged_summary_is_refused_as_no_work_done(tmp_path):
    _entry(tmp_path, "e1")
    v = ra.verdict_for("e1", "Old summary about Microsoft.", entries_dir=tmp_path)
    assert not v.ok
    assert any("unchanged" in p for p in v.problems)


def test_an_empty_or_missing_summary_is_refused(tmp_path):
    _entry(tmp_path, "e1")
    assert not ra.verdict_for("e1", "   ", entries_dir=tmp_path).ok


def test_an_unknown_id_is_refused_rather_than_creating_a_file(tmp_path):
    v = ra.verdict_for("ghost", "Anything at all here.", entries_dir=tmp_path)
    assert not v.ok
    assert not (tmp_path / "ghost.json").exists()


def test_apply_writes_only_the_accepted_ones(tmp_path):
    _entry(tmp_path, "good")
    _entry(tmp_path, "bad")
    results = {"good": "Microsoft is the subject of the piece.",
               "bad": "Salesforce is the subject."}
    report = ra.apply(results, entries_dir=tmp_path, write=True)
    assert json.loads((tmp_path / "good.json").read_text())["summary"].startswith("Microsoft")
    assert json.loads((tmp_path / "bad.json").read_text())["summary"] == "Old summary about Microsoft."
    assert report["applied"] == ["good"] and [r.id for r in report["refused"]] == ["bad"]


def test_dry_run_writes_nothing(tmp_path):
    _entry(tmp_path, "good")
    ra.apply({"good": "Microsoft is the subject of the piece."},
             entries_dir=tmp_path, write=False)
    assert json.loads((tmp_path / "good.json").read_text())["summary"] == "Old summary about Microsoft."


def test_apply_preserves_every_other_field_and_key_order(tmp_path):
    p = _entry(tmp_path, "e1", attribution="Someone", tags=["a", "b"])
    before = json.loads(p.read_text())
    ra.apply({"e1": "Microsoft is the subject of the piece."},
             entries_dir=tmp_path, write=True)
    after = json.loads(p.read_text())
    assert list(after) == list(before)
    assert {k: v for k, v in after.items() if k != "summary"} == \
           {k: v for k, v in before.items() if k != "summary"}


def test_a_batch_missing_ids_is_reported(tmp_path):
    _entry(tmp_path, "a")
    _entry(tmp_path, "b")
    missing = ra.missing_from(["a", "b"], {"a": "x"})
    assert missing == ["b"]
