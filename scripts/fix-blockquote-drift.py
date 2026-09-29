#!/usr/bin/env python3
"""Rewrite published blockquotes to a verbatim contiguous span of the stored source.

CLAUDE.md: blockquotes must be EXACT text from the source — never paraphrased,
composited, or summarised. `backfill-source-texts.py --audit` finds the ones that
drifted. This repairs them.

Method: word-level alignment. Anchor on the first and last few words of the
published quote, then take the source text between those anchors *verbatim*, which
restores whatever the published version silently dropped (an emoji, a smart quote,
an elided sentence). A rewrite is only accepted when every word of the published
quote still appears, in order, inside the span — so the quote can gain back what
was removed but can never change what it says.

If alignment would pull in far more than was published (a sign the quote was
stitched across distant paragraphs), falls back to the longest contiguous run that
matches the quote from its start, and only if that is still substantial.

Usage:
  python3 scripts/fix-blockquote-drift.py --dry-run
  python3 scripts/fix-blockquote-drift.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import source_texts  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ENTRIES = REPO / "content" / "entries"

WORD = re.compile(r"[0-9A-Za-zÀ-ÿЀ-ӿ]+")

MAX_GROWTH = 1.7      # span may be at most this many x the published word count
MAX_EXTRA_WORDS = 60  # ...and at most this many extra words, whichever is tighter
MIN_RUN_WORDS = 12    # a truncating fallback must keep at least this much


def words(s: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in WORD.finditer(s or "")]


CLOSERS = ".!?…\"'”’)]}»"


def extend(src: str, end: int) -> int:
    """Word matching ends at the last letter; pull in the punctuation that closes
    the sentence so quotes don't end mid-clause."""
    while end < len(src) and src[end] in CLOSERS:
        end += 1
    return end


def find_seq(hay: list[str], needle: list[str], start: int = 0) -> int:
    n = len(needle)
    for i in range(start, len(hay) - n + 1):
        if hay[i:i + n] == needle:
            return i
    return -1


def align(src: str, bq: str) -> tuple[str, str] | None:
    """Return (exact_span, method) or None."""
    sw, bw = words(src), words(bq)
    if len(bw) < 6:
        return None
    s_toks, b_toks = [w for w, _, _ in sw], [w for w, _, _ in bw]

    k = min(8, len(b_toks))
    i = find_seq(s_toks, b_toks[:k])
    if i < 0:
        return None

    # last anchor, searched after the first
    j_start = -1
    for kk in (8, 6, 4, 3):
        kk = min(kk, len(b_toks))
        pos, last = i, -1
        while True:
            p = find_seq(s_toks, b_toks[-kk:], pos)
            if p < 0:
                break
            last, pos = p, p + 1
        if last >= i:
            j_start = last + kk
            break

    if j_start > i:
        span = src[sw[i][1]:extend(src, sw[j_start - 1][2])]
        span_toks = [w for w, _, _ in words(span)]
        grew_ok = (
            len(span_toks) <= len(b_toks) * MAX_GROWTH
            and len(span_toks) - len(b_toks) <= MAX_EXTRA_WORDS
        )
        if grew_ok and subsequence(b_toks, span_toks):
            return span, "aligned"

    # Fallback: the longest contiguous run of the quote that exists verbatim in
    # the source — searched from every starting word, not just the first, so a
    # quote stitched as [short A … long B] keeps B rather than collapsing to A.
    best_len, best_at = 0, None
    for a in range(len(b_toks) - MIN_RUN_WORDS + 1):
        if len(b_toks) - a <= best_len:
            break  # can't beat the best from here
        lo, hi, longest = MIN_RUN_WORDS, len(b_toks) - a, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if find_seq(s_toks, b_toks[a:a + mid]) >= 0:
                longest, lo = mid, mid + 1
            else:
                hi = mid - 1
        if longest > best_len:
            best_len, best_at = longest, a
    if best_len >= MIN_RUN_WORDS:
        p = find_seq(s_toks, b_toks[best_at:best_at + best_len])
        return (src[sw[p][1]:extend(src, sw[p + best_len - 1][2])],
                f"longest verbatim run, {best_len}/{len(b_toks)} words")
    return None


def subsequence(needle: list[str], hay: list[str]) -> bool:
    it = iter(hay)
    return all(tok in it for tok in needle)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fixed, skipped = [], []
    for f in sorted(ENTRIES.glob("*.json")):
        e = json.loads(f.read_text(encoding="utf-8"))
        eid, bq = e.get("id"), e.get("blockquote")
        rec = source_texts.load(eid) if eid else None
        if not rec or not bq or rec.get("platform") == "transcript":
            continue
        if source_texts.contains_blockquote(eid, bq):
            continue

        got = align(rec["full_text"], bq)
        if not got:
            skipped.append((eid, "no confident alignment"))
            continue
        span, how = got
        fixed.append((eid, how, len(bq), len(span)))
        if not args.dry_run:
            e["blockquote"] = span
            f.write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    verb = "would rewrite" if args.dry_run else "rewrote"
    print(f"{verb} {len(fixed)} blockquote(s):")
    for eid, how, a, b in fixed:
        print(f"  ✓ {eid}\n      {how}; {a} -> {b} chars")
    print(f"\nleft alone: {len(skipped)}")
    for eid, why in skipped:
        print(f"  - {eid}  ({why})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
