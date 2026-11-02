#!/usr/bin/env python3
"""Build work packets for the legacy-summary rewrite pass.

    python3 scripts/rewrite_packets.py --out DIR [--batch-size 20] [--warnings]

Each packet is a JSON file holding everything a rewriter needs and nothing
else: the entry's own fields, its captured source text, its tier, and the
findings against it. The point is that a rewriter never has to go looking —
going looking is how a subagent ends up supplying a fact from its own head.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import summary_drift as sd
import summary_tics as st

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content" / "entries"

#: Rewrite the worst-affected types first; order drives batch numbering.
TYPE_ORDER = ["review", "endorsement", "reaction", "podcast", "event",
              "media", "social", "milestone"]


def packet_for(path: Path) -> dict | None:
    d = json.loads(path.read_text())
    summary = d.get("summary") or ""
    if not summary:
        return None
    tier = st.tier_for(d)
    findings = st.check(summary, d.get("blockquote"), tier)
    if not findings:
        return None
    cap = sd.capture_for(d["id"])
    return {
        "id": d["id"],
        "date": d["date"],
        "type": d.get("type"),
        "tier": tier,
        "target_words": st.TIER_TARGET[tier],
        "title": d.get("title"),
        "attribution": d.get("attribution"),
        "attribution_title": d.get("attribution_title"),
        "blockquote": d.get("blockquote"),
        "blockquote_source": d.get("blockquote_source"),
        "source_url": d.get("source_url"),
        "current_summary": summary,
        "current_words": len(summary.split()),
        "findings": [{"rule": f.rule, "severity": f.severity,
                      "message": f.message, "span": f.span} for f in findings],
        "has_capture": cap is not None,
        # Truncated: a rewriter needs the gist and the facts, not 6,000 words.
        "source_text": (cap[:4000] + " …[truncated]" if cap and len(cap) > 4000 else cap),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--warnings", action="store_true",
                    help="include entries with only warnings (default: failures only)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    packets = []
    for p in sorted(ENTRIES.glob("*.json")):
        pk = packet_for(p)
        if not pk:
            continue
        hard = any(f["severity"] == "fail" for f in pk["findings"])
        if hard or args.warnings:
            packets.append(pk)

    packets.sort(key=lambda x: (TYPE_ORDER.index(x["type"]) if x["type"] in TYPE_ORDER
                                else len(TYPE_ORDER), x["date"]))
    n = 0
    for i in range(0, len(packets), args.batch_size):
        chunk = packets[i:i + args.batch_size]
        n += 1
        (args.out / f"batch-{n:02d}.json").write_text(json.dumps(chunk, indent=2) + "\n")
    print(f"{len(packets)} entries -> {n} batches of up to {args.batch_size} in {args.out}")
    import collections
    print("  by type:", dict(collections.Counter(p["type"] for p in packets)))
    print("  by tier:", dict(collections.Counter(p["tier"] for p in packets)))
    print("  with captured source text:",
          sum(1 for p in packets if p["has_capture"]), "/", len(packets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
