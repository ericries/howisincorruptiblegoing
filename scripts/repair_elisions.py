"""Mark the cuts in blockquotes that silently elide source material.

    python3 scripts/repair_elisions.py            # report what is repairable
    python3 scripts/repair_elisions.py --apply    # rewrite those entries

Backfilling source text (scripts/backfill_source_text.py) turned up a recurring
shape: a blockquote built from real source spans, in source order, with unmarked
gaps between them. The 2026-02-12 site-launch entry runs "...aligned brand
partner." straight into a sentence two sentences later, skipping "Huge thanks to
Wunderdogs for building incorruptible.co in record time."

The words are real and the trim is usually sound editing. What is wrong is that
the cut is invisible — which is exactly what CLAUDE.md forbids with "never
paraphrase, composite, or summarize". A reader cannot tell that the two halves
were not adjacent, and in the worst case the join changes the meaning. A
composited quote already survived three months in this repo with half a sentence
belonging to Brian Chesky.

Marking each cut with an ellipsis keeps the editorial selection and makes the
removal visible, which is ordinary quotation practice.

SAFETY: a repair is applied only when every segment is verbatim in the source
AND the segments appear in source order. If either fails, the entry is reported
and left alone. A repairer that guesses would quietly rewrite quotes into
something nobody said, which is the failure it exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quote_integrity import (  # noqa: E402
    ENTRIES,
    Verdict,
    check_entry,
    load_capture,
    normalise,
)

ELLIPSIS = "…"

# A segment shorter than this is not a quotation, it is a fragment of grammar.
# Splitting on every stray word produces confetti rather than a readable quote.
MIN_SEGMENT = 25

# Give up rather than produce a quote peppered with cuts. Something that
# fragments this badly is not an elision; it is a paraphrase, and a person
# should look at it.
MAX_SEGMENTS = 4


def _longest_prefix_in(text: str, source: str) -> int:
    """Length of the longest prefix of `text` that appears verbatim in `source`."""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if text[:mid] in source:
            lo = mid
        else:
            hi = mid - 1
    return lo


def segment_quote(quote: str, source: str) -> list[str] | None:
    """Split `quote` into the verbatim source spans it is made of.

    Returns None when the quote cannot be accounted for entirely by in-order
    verbatim spans — which is the signal that something was invented, reordered
    or paraphrased, and that a human should look rather than a script.
    """
    quote = (quote or "").strip()
    if not quote or not source:
        return None
    if quote in source:
        return [quote]

    segments: list[str] = []
    rest = quote
    last_pos = -1
    while rest:
        rest = rest.lstrip(" " + ELLIPSIS)
        if not rest:
            break
        n = _longest_prefix_in(rest, source)
        if n < MIN_SEGMENT:
            return None
        seg = rest[:n].rstrip()
        # Trim back to a whole word only when the cut actually lands inside a
        # token. Trimming unconditionally chopped "…aligned brand partner."
        # back to "…aligned brand", because the match had simply run on into
        # the following space.
        nxt = rest[n:n + 1]
        if seg and nxt and nxt.isalnum() and seg[-1].isalnum():
            cut = seg.rfind(" ")
            if cut < MIN_SEGMENT:
                return None
            seg = seg[:cut]
        pos = source.find(seg)
        if pos <= last_pos:
            return None                 # out of order: a rewrite, not an elision
        last_pos = pos
        segments.append(seg)
        rest = rest[len(seg):]
        if len(segments) > MAX_SEGMENTS:
            return None
    return segments or None


def repair_quote(quote: str, source: str) -> str | None:
    """The quote with each elision marked, or None if it cannot be done safely."""
    segs = segment_quote(quote, source)
    if not segs:
        return None
    if len(segs) == 1:
        return segs[0]
    return f" {ELLIPSIS} ".join(segs)


# --- applying across the corpus ---------------------------------------------------------

def candidates() -> list[dict]:
    """Entries whose quote fails against its capture and might be an elision."""
    out = []
    for f in sorted(ENTRIES.glob("*.json")):
        try:
            e = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        r = check_entry(e)
        if not r.verdict.is_failure:
            continue
        cap = load_capture(e.get("id", "")) or {}
        src = cap.get("full_text") or ""
        if not src:
            continue
        fixed = repair_quote(e.get("blockquote", ""), src)
        out.append({"path": f, "entry": e, "source": src,
                    "verdict": r.verdict, "fixed": fixed})
    return out


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = candidates()
    repairable = [r for r in rows if r["fixed"]]
    stuck = [r for r in rows if not r["fixed"]]

    for r in repairable:
        e = r["entry"]
        n = r["fixed"].count(ELLIPSIS)
        print(f"{'repair' if args.apply else 'would repair'} {e['id']}  "
              f"({r['verdict'].value}, {n} cut{'s' if n != 1 else ''})")
        if args.apply:
            e["blockquote"] = r["fixed"]
            r["path"].write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n")

    print(f"\n{len(repairable)} repairable, {len(stuck)} need a human:")
    for r in stuck:
        print(f"  {r['entry']['id']}  ({r['verdict'].value})")

    if args.apply:
        still = [r for r in candidates() if r["fixed"]]
        print(f"\nafter repair: {len(still)} still repairable (should be 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
