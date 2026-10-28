"""A dataset read must not return less than the dataset holds.

On 2026-10-28 `scan-triage.py --archive` wrote 60 items to a raw archive file
from a dataset that held 246, and said "archived 60 items" with no error. The run
was still writing; `fetch()` polled once, saw 60 items, and returned because its
stopping condition was `len(items) >= expect` with `expect` defaulting to 1.

That archive file is what every downstream judgement reads — including
`feed_coverage`, whose whole job is spotting missing days. A partial archive is
indistinguishable from a quiet day, so the failure is silent by construction and
was caught only because an unrelated billing lookup happened to disagree.

These tests pin the stopping condition to the dataset's own `itemCount`.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# The module has a hyphen in its name, so it cannot be imported normally.
_SPEC = importlib.util.spec_from_file_location(
    "scan_triage", Path(__file__).resolve().parent / "scan-triage.py")
scan_triage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scan_triage)


class FakeDataset:
    """An Apify dataset that fills in over several polls, as a live run does."""

    def __init__(self, reads: list[list[dict]], item_count: int):
        self.reads = list(reads)
        self.item_count = item_count
        self.n_item_calls = 0

    def items(self, _dataset_id):
        self.n_item_calls += 1
        return self.reads[min(self.n_item_calls - 1, len(self.reads) - 1)]

    def meta(self, _dataset_id):
        return {"itemCount": self.item_count}


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(scan_triage.time, "sleep", lambda _s: None)


def wire(monkeypatch, fake: FakeDataset):
    monkeypatch.setattr(scan_triage, "_read_items", fake.items)
    monkeypatch.setattr(scan_triage, "dataset_meta", fake.meta)


def item(n: int) -> dict:
    return {"id": f"i{n}"}


# --- the stopping condition ---------------------------------------------------------

def test_fetch_waits_until_the_read_matches_item_count(monkeypatch, no_sleep):
    """The exact 2026-10-28 shape: a partial first read on a still-running job."""
    partial = [item(i) for i in range(60)]
    full = [item(i) for i in range(246)]
    fake = FakeDataset(reads=[partial, partial, full], item_count=246)
    wire(monkeypatch, fake)

    got = scan_triage.fetch("d1")

    assert len(got) == 246
    assert fake.n_item_calls == 3, "should have kept polling past the partial reads"


def test_fetch_returns_immediately_when_already_complete(monkeypatch, no_sleep):
    full = [item(i) for i in range(39)]
    fake = FakeDataset(reads=[full], item_count=39)
    wire(monkeypatch, fake)

    assert len(scan_triage.fetch("d1")) == 39
    assert fake.n_item_calls == 1, "a complete dataset must not cost extra polls"


def test_fetch_accepts_a_genuinely_empty_dataset(monkeypatch, no_sleep):
    """A zero-result query is a real outcome, not something to poll 20 times for.

    2026-10-25's keyword pull returned 0 items legitimately. Treating empty as
    'not ready yet' would burn 200 seconds on every quiet day.
    """
    fake = FakeDataset(reads=[[]], item_count=0)
    wire(monkeypatch, fake)

    assert scan_triage.fetch("d1") == []
    assert fake.n_item_calls == 1


def test_fetch_polls_again_when_the_count_outruns_the_read(monkeypatch, no_sleep):
    """itemCount is read after the items, so concurrent writes cost a poll.

    The first read lands 100 rows while the run has already written 150. Taking
    the count second surfaces that as count > n_read; taking it first would have
    called the stale read complete.
    """
    fake = FakeDataset(reads=[[item(i) for i in range(100)],
                              [item(i) for i in range(150)]], item_count=150)
    wire(monkeypatch, fake)

    assert len(scan_triage.fetch("d1")) == 150
    assert fake.n_item_calls == 2


def test_fetch_gives_up_after_tries_and_returns_what_it_has(monkeypatch, no_sleep):
    """Never hang forever; a short read is still better than nothing, loudly."""
    partial = [item(i) for i in range(10)]
    fake = FakeDataset(reads=[partial], item_count=99)
    wire(monkeypatch, fake)

    got = scan_triage.fetch("d1", tries=3)

    assert len(got) == 10
    assert fake.n_item_calls == 3


def test_fetch_survives_missing_item_count(monkeypatch, no_sleep):
    """If the metadata endpoint fails, fall back rather than blocking the scan."""
    fake = FakeDataset(reads=[[item(1)]], item_count=0)
    monkeypatch.setattr(scan_triage, "_read_items", fake.items)
    monkeypatch.setattr(scan_triage, "dataset_meta",
                        lambda _d: (_ for _ in ()).throw(OSError("boom")))

    assert len(scan_triage.fetch("d1")) == 1


# --- refusing to archive a partial read ---------------------------------------------

def test_is_complete_true_when_counts_match():
    assert scan_triage.is_complete(n_read=246, item_count=246) is True


def test_is_complete_false_when_short():
    assert scan_triage.is_complete(n_read=60, item_count=246) is False


def test_is_complete_true_when_item_count_unknown():
    """Unknown completeness must not block archiving — only known-short does."""
    assert scan_triage.is_complete(n_read=60, item_count=None) is True


def test_is_complete_true_when_read_exceeds_count():
    """itemCount can lag the items endpoint; more than expected is not a failure."""
    assert scan_triage.is_complete(n_read=250, item_count=246) is True


def test_archive_refuses_to_overwrite_with_a_short_read(tmp_path, capsys):
    """The file is the record. A silent partial overwrite destroys evidence."""
    target = tmp_path / "2026-10-28-author.json"
    target.write_text(json.dumps([item(i) for i in range(246)]))

    wrote = scan_triage.archive(target, [item(i) for i in range(60)], item_count=246)

    assert wrote is False
    assert len(json.loads(target.read_text())) == 246, "existing archive must survive"
    assert "partial" in capsys.readouterr().err.lower()


def test_archive_writes_a_complete_read(tmp_path):
    target = tmp_path / "out.json"
    assert scan_triage.archive(target, [item(i) for i in range(39)], item_count=39) is True
    assert len(json.loads(target.read_text())) == 39


def test_archive_writes_when_no_file_exists_even_if_short(tmp_path, capsys):
    """Nothing to destroy, so keep the data — but say plainly that it is short."""
    target = tmp_path / "new.json"
    assert scan_triage.archive(target, [item(1)], item_count=99) is True
    assert "partial" in capsys.readouterr().err.lower()
