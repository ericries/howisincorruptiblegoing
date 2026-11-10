#!/usr/bin/env python3
"""Did a rewritten summary invent anything?

    python3 scripts/summary_drift.py --vs-head content/entries/*.json

WHY THIS EXISTS

Rewriting ~400 legacy summaries means delegating, and a subagent asked to make
a summary clearer will supply the clarity it needs — a job title, a company, a
round number — whether or not the entry supports it. Nobody catches that by
reading 400 diffs, and it is the one failure that would make the whole pass
worse than leaving the summaries alone.

So the boundary is asserted rather than trusted. Every proper noun and number
in the new summary must already appear in one of its sources: the previous
summary, the blockquote, the title, or the captured source text in
data/archive/source-texts/. Anything new is reported by name.

This cannot prove a rewrite is faithful — it catches invented ENTITIES, not
invented relationships between real ones ("Courtois chairs Microsoft" passes).
Pair it with the read-through; it is a net, not a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "data" / "archive" / "source-texts"

_NUM_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
    "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100",
    "thousand": "1000", "million": "1000000", "billion": "1000000000",
}

#: Sentence-initial capitals are usually grammar, not names — but nearly every
#: summary here OPENS with a name, so skipping them wholesale left the commonest
#: position unchecked. Only these ordinary openers are excused; anything else in
#: that slot is still tested against the sources, and an ordinary word passes
#: simply by appearing in them.
_SENT_START = re.compile(r"(?:^|[.!?:;]\s+|—\s+)([A-Z])")
_OPENERS = {
    "the", "a", "an", "he", "she", "it", "they", "his", "her", "their", "its",
    "this", "that", "these", "those", "there", "here", "in", "on", "at", "by",
    "hers", "theirs", "ours", "mine", "we", "our", "my", "him", "them", "us",
    "for", "from", "with", "when", "while", "after", "before", "both", "but",
    "and", "as", "if", "so", "then", "one", "two", "three", "each", "every",
    "no", "not", "all", "some", "most", "many", "what", "where", "who", "how",
    "writing", "speaking", "asked", "posting", "reading", "published", "called",
}
#: A run of capitalised tokens: "Sequoia Capital", "Jean-Philippe Courtois".
_ENTITY = re.compile(r"\b[A-Z][\w'’-]*(?:\s+(?:of|de|the|and)\s+[A-Z][\w'’-]*|\s+[A-Z][\w'’-]*)*")
_NUMBER = re.compile(r"\b\d[\d,.]*\b")

#: Never a "lost fact" when a rewrite stops saying it.
_ALWAYS_KEPT = {"incorruptible", "eric", "ries", "eric ries",
                "frames", "tags", "publishes", "says", "argues", "notes"}


def _norm(tok: str) -> str:
    t = tok.strip().rstrip(".,;:")
    t = re.sub(r"['’]s$", "", t)              # possessive -> bare
    return t.lower().replace(",", "")


def _numbers(text: str) -> set[str]:
    out = {_norm(m.group(0)).rstrip(".") for m in _NUMBER.finditer(text)}
    for word, digits in _NUM_WORDS.items():
        if re.search(rf"\b{word}\b", text, re.I):
            out.add(digits)
    return {x for x in out if x}


def _entities(text: str) -> list[str]:
    starts = {m.start(1) for m in _SENT_START.finditer(text)}
    found = []
    for m in _ENTITY.finditer(text):
        if (m.start() in starts and " " not in m.group(0)
                and _norm(m.group(0)) in _OPENERS):
            continue        # ordinary grammar, not a name
        found.append(m.group(0).strip())
    return found


def _haystack(*sources: str | None) -> tuple[str, set[str]]:
    text = " ".join(s for s in sources if s)
    return text.lower(), _numbers(text)


def introduced(new: str, old: str | None = None, blockquote: str | None = None,
               title: str | None = None, source_text: str | None = None,
               attribution: str | None = None,
               attribution_title: str | None = None,
               blockquote_source: str | None = None,
               entry_date: str | None = None) -> list[str]:
    """Proper nouns and numbers in `new` that none of the sources contain.

    attribution and attribution_title were missing from this list at first,
    which cost six rewrites their orienting detail — "Founder (YC S18); former
    PM at Airbnb and Google" and the like. Those fields are part of the entry
    and are printed on the card, so the most orienting text on the page was
    the one thing a rewrite was not allowed to draw on.
    """
    hay, hay_nums = _haystack(old, blockquote, title, source_text,
                              attribution, attribution_title, blockquote_source,
                              entry_date)
    out: list[str] = []

    for ent in _entities(new):
        bare = _norm(ent)
        if bare and bare not in hay:
            # A multi-word name whose every part is known is not new.
            parts = [_norm(p) for p in ent.split()]
            if all(p in hay for p in parts if p):
                continue
            if ent not in out:
                out.append(ent)

    # Report numbers as they were written, not as they were normalised for
    # comparison — "30,000" is what a reader has to go and check.
    for m in _NUMBER.finditer(new):
        raw = m.group(0).rstrip(".,;:")
        if _norm(raw).rstrip(".") not in hay_nums and raw not in out:
            out.append(raw)
    return out


def dropped(old: str, new: str, blockquote: str | None = None) -> list[str]:
    """Entities and numbers the rewrite threw away, that no quote preserves.

    The mirror of `introduced`. The first rewrite pass padded; correcting the
    brief made the second pass cut, and cutting is the harder failure to see —
    a shorter summary always looks like progress. Steve Blank went 68 words to
    28 and lost "intellectual godfather of the lean-startup movement" along
    with the tics.

    A fact still carried by the blockquote is not lost: dropping it from the
    summary is the echo rule working as intended. Only facts that survive in
    neither place are reported.
    """
    kept, _ = _haystack(new, blockquote)
    kept_nums = _numbers(new) | _numbers(blockquote or "")
    out: list[str] = []
    for ent in _entities(old):
        bare = _norm(ent)
        if not bare or bare in kept or ent in out:
            continue
        # House style shortens to a surname after first reference, and every
        # entry is about the book — neither is a lost fact. Without this the
        # check reported something for 39 of 40 rewrites and buried the real
        # losses (SVPG, Glitch CEO, NAMB, Wolfson College) in the noise.
        if any(_norm(w) in kept for w in ent.split() if _norm(w)):
            continue
        if bare in _ALWAYS_KEPT:
            continue
        out.append(ent)
    for m in _NUMBER.finditer(old):
        raw = m.group(0).rstrip(".,;:")
        if _norm(raw).rstrip(".") not in kept_nums and raw not in out:
            out.append(raw)
    return out


def _head_field(path: Path, field: str) -> str | None:
    rel = Path(path).resolve().relative_to(ROOT)
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get(field)
    except json.JSONDecodeError:
        return None


def capture_for(entry_id: str) -> str | None:
    p = CAPTURES / f"{entry_id}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    text = d.get("full_text") or d.get("text") or None
    # An entry can gain a second source after it ships — an organiser's own
    # programme page confirming a workshop first seen in a participant's post.
    # That is evidence, so the summary may rest on it; it is kept OUT of
    # `full_text` because `quote_integrity` checks the blockquote against the
    # one source it was taken from, and merging two would mis-source it.
    extra = [str(c.get("text") or "") for c in (d.get("corroborating_sources") or [])
             if isinstance(c, dict)]
    extra = [t for t in extra if t.strip()]
    if not extra:
        return text
    return "\n\n".join([t for t in [text, *extra] if t])


def check_entry_vs_head(path: Path) -> list[str] | None:
    d = json.loads(Path(path).read_text())
    new = d.get("summary") or ""
    old = _head_field(path, "summary")
    if old is None or new == old:
        return None
    return introduced(new, old=old, blockquote=d.get("blockquote"),
                      title=d.get("title"), source_text=capture_for(d["id"]),
                      attribution=d.get("attribution"),
                      attribution_title=d.get("attribution_title"),
                      blockquote_source=d.get("blockquote_source"),
                      entry_date=d.get("date"))


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--vs-head", action="store_true", default=True)
    args = ap.parse_args()

    flagged = checked = 0
    for p in args.files:
        if not p.exists():
            continue
        got = check_entry_vs_head(p)
        if got is None:
            continue
        checked += 1
        if got:
            flagged += 1
            print(f"\n❌ {p.name}\n   not in the old summary, blockquote, title "
                  f"or capture: {', '.join(repr(g) for g in got)}")
    print(f"\nSummary drift: {checked} rewritten, {flagged} introducing unsourced detail.")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(_main())
