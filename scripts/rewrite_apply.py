#!/usr/bin/env python3
"""Apply subagent summary rewrites, refusing the ones that don't hold up.

    python3 scripts/rewrite_apply.py result-01.json            # dry run
    python3 scripts/rewrite_apply.py --write result-01.json
    python3 scripts/rewrite_apply.py --write --batch batch-01.json result-01.json

WHY THIS EXISTS

The risk in delegating 253 rewrites is not a clumsy sentence — those are
readable. It is a rewrite that is fluent and wrong: a job title supplied from
the model's own head, a number rounded, an id quietly dropped. None of those
is visible in a 253-file diff.

So every rewrite has to clear the same gates the hook applies, BEFORE it is
written to disk, and a refusal leaves the old summary in place rather than
shipping something unverified. Pass --batch to also report ids the subagent
was given and did not return.
"""

from __future__ import annotations

import argparse
import collections
import json
from dataclasses import dataclass, field
from pathlib import Path

import summary_drift as sd
import summary_tics as st

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content" / "entries"


@dataclass
class Verdict:
    id: str
    ok: bool = True
    problems: list[str] = field(default_factory=list)
    new: str | None = None
    warnings: list[str] = field(default_factory=list)


def verdict_for(entry_id: str, new: str, entries_dir: Path = ENTRIES) -> Verdict:
    v = Verdict(entry_id, new=new)
    path = Path(entries_dir) / f"{entry_id}.json"
    if not path.exists():
        v.ok = False
        v.problems.append(f"no entry file for id {entry_id!r}")
        return v

    d = json.loads(path.read_text())
    new = (new or "").strip()
    if not new:
        v.ok = False
        v.problems.append("empty summary")
        return v
    if new == (d.get("summary") or "").strip():
        v.ok = False
        v.problems.append("unchanged from the existing summary — no work done")
        return v

    for f in st.check(new, d.get("blockquote"), st.tier_for(d)):
        if f.severity == "fail":
            v.ok = False
            v.problems.append(f"[{f.rule}] {f.message}"
                              + (f" -> {f.span!r}" if f.span else ""))
        else:
            v.warnings.append(f"[{f.rule}] {f.message}")

    invented = sd.introduced(new, old=d.get("summary"), blockquote=d.get("blockquote"),
                             title=d.get("title"), source_text=sd.capture_for(entry_id))
    if invented:
        v.ok = False
        v.problems.append("unsourced detail: " + ", ".join(repr(x) for x in invented))

    v.new = new
    return v


def missing_from(batch_ids: list[str], results: dict) -> list[str]:
    return [i for i in batch_ids if i not in results]


def apply(results: dict[str, str], entries_dir: Path = ENTRIES,
          write: bool = False) -> dict:
    applied, refused = [], []
    for eid, new in results.items():
        v = verdict_for(eid, new, entries_dir)
        if not v.ok:
            refused.append(v)
            continue
        if write:
            path = Path(entries_dir) / f"{eid}.json"
            d = json.loads(path.read_text(), object_pairs_hook=collections.OrderedDict)
            d["summary"] = v.new
            with path.open("w") as f:
                json.dump(d, f, indent=2, ensure_ascii=True)
                f.write("\n")
        applied.append(eid)
    return {"applied": applied, "refused": refused}


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--batch", type=Path, help="the packet, to report unreturned ids")
    args = ap.parse_args()

    merged: dict[str, str] = {}
    for r in args.results:
        merged.update(json.loads(r.read_text()))

    if args.batch:
        given = [p["id"] for p in json.loads(args.batch.read_text())]
        gone = missing_from(given, merged)
        if gone:
            print(f"⚠  {len(gone)} id(s) in the packet were not returned:")
            for g in gone:
                print(f"   {g}")

    report = apply(merged, write=args.write)
    for v in report["refused"]:
        print(f"\n❌ {v.id}")
        for p in v.problems:
            print(f"   {p}")
    warned = [v for v in report["refused"] if v.warnings]
    mode = "applied" if args.write else "would apply (dry run)"
    print(f"\nRewrites: {len(report['applied'])} {mode}, "
          f"{len(report['refused'])} refused.")
    return 1 if report["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(_main())
