#!/usr/bin/env python3
"""Flag AI-ese in entry summaries.

    python3 scripts/summary_tics.py content/entries/*.json      # check
    python3 scripts/summary_tics.py --trend                     # length by month

WHY THIS EXISTS

CLAUDE.md has said summaries are "concise, 1-2 sentences" since the site was
built. Measured on 2026-11-01, the median summary ran 20 words in January and
102 in November — a monotonic five-fold drift that nobody chose. Eric found it
by reading one: "careful about AI-ese, this reads like LLM speak."

A prose rule in a file nothing reads gives you no reference point, so every
summary looks reasonable beside the one before it. That is the whole failure.

The rules split by how sure a machine can be:

  FAIL — objective. Length. A word off the blacklist. The summary quoting the
         blockquote back at the reader. The corrective antithesis ("not X,
         but Y"), which is the single most recognisable LLM tell and is almost
         never the clearest way to say a thing.

  WARN — devices that are good writing once and a tell when they saturate:
         em dashes, tricolons, moral framing of my own process. Reported with
         the offending span so a person can judge. Never blocks.

Sources for the rule set: Colin Gorrie, "Why ChatGPT writes like that"
(parallelism / antithesis / tricolon as the three overused devices);
github.com/finngi/tics (27 deterministic rules, five categories);
github.com/conorbronsdon/avoid-ai-writing (narrated candor, invented
contrasts, moral adjectives). See docs/DRAFTING.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Length targets by tier. Eric, 2026-11-01: "1-2 sentences is not a hard rule.
#: we want to make them as good as is appropriate, with the more important
#: milestones getting more attention. but the focus shuld still be on a concise
#: description tha tmakes clear what's going on to someone who may not have the
#: context needed."
#:
#: So length is a WARNING against a tier target, not a failure. What a machine
#: can still be sure about is bloat: past HARD_CEILING nothing is earning its
#: words, and the original 127-word offender sat under it, so the ceiling is
#: not the real check — the tics and the tier target are.
TIER_TARGET = {
    "major": 110,    # milestones, flagged endorsements, anything in the rails
    "standard": 75,  # reviews, podcasts, media, events
    "brief": 55,     # reactions, social, passing mentions
}
HARD_CEILING = 150

#: Types that get the standard target when nothing flags them as major.
_STANDARD_TYPES = {"review", "podcast", "media", "event", "endorsement", "milestone"}


def tier_for(entry: dict) -> str:
    tm = entry.get("type_metadata") or {}
    if tm.get("highlight") or tm.get("featured") or tm.get("sidebar_quote"):
        return "major"
    if entry.get("type") == "milestone":
        return "major"
    return "standard" if entry.get("type") in _STANDARD_TYPES else "brief"

#: Corporate AI-ese. Short on purpose — a blacklist that grows past what is
#: genuinely dead gives false positives on ordinary words, and this site's
#: problem was never "delve", it was the literary register.
BUZZWORDS = [
    "delve", "leverage", "tapestry", "testament", "realm", "beacon",
    "robust", "pivotal", "seamless", "multifaceted", "underscore",
    "cutting-edge", "game-changer", "transformative", "unlock", "unleash",
    "myriad", "plethora", "showcase", "landscape of",
]

#: Abbreviations whose full stop does not end a sentence.
_ABBREV = r"(?<!\bInc)(?<!\bLtd)(?<!\bCo)(?<!\bCorp)(?<!\bDr)(?<!\bMr)(?<!\bMs)(?<!\bMrs)(?<!\bSt)(?<!\bvs)(?<!\bU\.S)(?<!\bPh\.D)"

_CORRECTIVE_TAIL = r"\s*[,—–]\s*(?:but|it's|it is|rather|they're|they are)\b"
_ANTITHESIS = [
    # "is not X, but Y"
    re.compile(r"\b(?:is|are|was|were|it's)\s+not\s+[^,.;—]{2,70}" + _CORRECTIVE_TAIL, re.I),
    # the contracted form carries its own negative: "isn't X — it's Y"
    re.compile(r"\b(?:isn't|aren't|wasn't|weren't)\s+[^,.;—]{2,70}" + _CORRECTIVE_TAIL, re.I),
    # "not X but Y" with no comma
    re.compile(r"\bnot\s+(?:just|only|merely|simply)\s+[^,.;]{2,70}\s+but\b", re.I),
    # the appositive: "…, not her coinage." — a corrective tacked on the end
    re.compile(r",\s*not\s+(?:a|an|the|his|her|its|their|my|our)\s+[\w' -]{2,45}(?=[.;]|$)", re.I),
]

# Double quotes and matched curly singles only. A bare ' or ’ is an
# apostrophe far more often than a quote mark, and treating it as one made
# "isn't a note — it's the argument" strip down to "isn s the argument",
# silently disabling every other rule on any summary with two apostrophes.
#: Words that were true the day the summary was written and wrong ever after.
#: An entry is a dated record sitting next to its own date, so a relative time
#: word freezes into it. "upcoming" did exactly that in six entries whose events
#: happened months ago, and "last Thursday" went into a rewrite on 2026-11-01.
#: Use the absolute date, or say nothing.
_RELATIVE_TIME = re.compile(
    r"\b(?:"
    r"upcoming|tomorrow|yesterday|recently|currently|nowadays|"
    r"(?:just|only)\s+(?:now|today)|right\s+now|these\s+days|at\s+present|"
    r"(?:last|next|this)\s+(?:week|month|year|night|spring|summer|autumn|fall|winter|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"this\s+(?:coming|past)|a\s+few\s+(?:days|weeks|months)\s+ago|"
    r"(?:earlier|later)\s+(?:this|next|last)\s+(?:week|month|year)"
    r")\b", re.I)

_QUOTED = re.compile(r"\"[^\"]{3,}?\"|“[^”]{3,}?”|«[^»]{3,}?»|‘[^’]{3,}?’")


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str   # "fail" | "warn"
    message: str
    span: str | None = None


def sentences(text: str) -> list[str]:
    parts = re.split(_ABBREV + r"(?<=[.!?])\s+(?=[A-Z\"“'(])", text.strip())
    return [p for p in parts if p.strip()]


def _strip_quoted(text: str) -> str:
    """Someone else's words are not mine to be judged on."""
    return _QUOTED.sub(" ", text)


def _shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    w = re.findall(r"[\w']+", text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def check(summary: str, blockquote: str | None = None,
          tier: str = "standard") -> list[Finding]:
    out: list[Finding] = []
    if not summary or not summary.strip():
        return out
    unquoted = _strip_quoted(summary)

    n_sent, n_word = len(sentences(summary)), len(summary.split())
    target = TIER_TARGET.get(tier, TIER_TARGET["standard"])
    if n_word > HARD_CEILING:
        out.append(Finding(
            "length", "fail",
            f"{n_sent} sentences / {n_word} words. Past {HARD_CEILING} nothing is "
            f"earning its words. Cut the sentence restating the blockquote and the "
            f"one narrating your research, then judge the rest."))
    elif n_word > target:
        out.append(Finding(
            "length", "warn",
            f"{n_sent} sentences / {n_word} words against a {tier} target of "
            f"{target}. Fine if every word orients a reader with no context; "
            f"not fine if it summarises the source instead of introducing it."))

    for rx in _ANTITHESIS:
        m = rx.search(unquoted)
        if m:
            out.append(Finding(
                "antithesis", "fail",
                "the corrective antithesis ('not X, but Y') is the most "
                "recognisable LLM tell. Say the thing you mean and drop the "
                "half you don't.", m.group(0).strip()))
            break

    # "Tomorrow's Company" is an organisation Mark Goyder founded in 1996, not a
    # relative time word, and on 2026-11-09 this rule failed a summary for naming
    # it. A gate that cannot tell a proper noun from a time word pushes the writer
    # to mangle the name to satisfy it. Possessive-capitalised use is a name.
    _PROPER = re.compile(r"\b(?:Tomorrow|Yesterday)'s\s+[A-Z]")
    scanned = _PROPER.sub("", unquoted)
    m = _RELATIVE_TIME.search(scanned)
    if m:
        out.append(Finding(
            "relative-time", "fail",
            "a relative time word freezes into a dated record and is wrong from "
            "the next day on. Use the absolute date, or drop it.", m.group(0)))

    low = unquoted.lower()
    for w in BUZZWORDS:
        if re.search(rf"\b{re.escape(w)}\b", low):
            out.append(Finding("buzzword", "fail",
                               f"'{w}' is on the blacklist; use the plain word.", w))
            break

    if blockquote:
        shared = _shingles(summary) & _shingles(blockquote)
        if shared:
            out.append(Finding(
                "echoes-blockquote", "fail",
                "the summary quotes the blockquote back at the reader, which is "
                "printed directly below it. Introduce the quote; don't preview it.",
                " ".join(sorted(shared)[0])))

    # ── saturation warnings ──────────────────────────────────────────────
    # Count ASIDES, not dashes. A matched pair inside one sentence is a single
    # parenthetical — the device used correctly — so "Cantrill — its CTO — spent"
    # is one aside. Two dashes in separate sentences are two.
    asides = sum(-(-sent.count("\u2014") // 2) for sent in sentences(summary))
    if asides > 1:
        dashes = summary.count("\u2014")
        out.append(Finding("em-dash", "warn",
                           f"{asides} em-dash asides ({dashes} dashes) in {n_word} words. "
                           f"One sharp aside is fine; a second usually means a sentence "
                           f"wants splitting."))

    if re.search(r"[^,.;:]{8,},[^,.;:]{8,},[^,.;:]{8,}?,?\s+and\s", unquoted):
        out.append(Finding("tricolon", "warn",
                           "a three-item parallel list. Fine once — a tell when every "
                           "summary has one. Two items often carry the same meaning."))

    m = re.search(r"\b(?:the honest (?:answer|place|thing|shape)|honestly|genuinely|"
                  r"truly|I would rather|worth saying|to be fair|candidly)\b", unquoted, re.I)
    if m:
        out.append(Finding("narrated-candor", "warn",
                           "moral framing of your own process. State the fact; the "
                           "reader decides whether it was honest.", m.group(0)))

    return out


def check_entry(path: Path) -> list[Finding]:
    d = json.loads(Path(path).read_text())
    return check(d.get("summary") or "", d.get("blockquote"), tier_for(d))


def _head_summary(path: Path) -> str | None:
    """The summary as committed, or None if the file is new."""
    import subprocess
    rel = Path(path).resolve().relative_to(ROOT)
    out = subprocess.run(["git", "show", f"HEAD:{rel}"],
                         cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout).get("summary")
    except json.JSONDecodeError:
        return None


def check_file_vs_head(path: Path) -> list[Finding] | None:
    """Check only summaries this commit actually writes.

    404 of 889 summaries predate the rules and failing on all of them would
    make the hook useless — every unrelated edit to an old entry would be
    blocked by prose written in May. So: a new entry is checked, a rewritten
    summary is checked, and an entry whose summary is untouched is skipped.
    New drift is impossible; the backlog stays visible via a bare run.

    Returns None when there is nothing to check.
    """
    d = json.loads(Path(path).read_text())
    summary = d.get("summary") or ""
    if summary == _head_summary(path):
        return None
    return check(summary, d.get("blockquote"), tier_for(d))


def _trend() -> int:
    import collections
    import statistics
    by = collections.defaultdict(list)
    for f in sorted((ROOT / "content" / "entries").glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("summary"):
            by[d["date"][:7]].append(len(d["summary"].split()))
    print(f"{'month':9}{'n':>5}{'median words':>14}")
    for m in sorted(by):
        print(f"{m:9}{len(by[m]):5d}{statistics.median(by[m]):14.0f}")
    return 0


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--trend", action="store_true", help="median summary length by month")
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    ap.add_argument("--vs-head", action="store_true",
                    help="check only summaries this commit rewrites (for the hook)")
    args = ap.parse_args()

    if args.trend:
        return _trend()
    if not args.files:
        ap.error("give entry files, or --trend")

    failed = warned = skipped = 0
    for p in args.files:
        if not p.exists():
            continue
        found = check_file_vs_head(p) if args.vs_head else check_entry(p)
        if found is None:
            skipped += 1
            continue
        hard = [f for f in found if f.severity == "fail"]
        soft = [f for f in found if f.severity == "warn"]
        failed += bool(hard)
        warned += bool(soft)
        for f in hard:
            print(f"\n❌ {p.name}\n   [{f.rule}] {f.message}"
                  + (f"\n   -> {f.span!r}" if f.span else ""))
        if not args.quiet:
            for f in soft:
                print(f"\n⚠  {p.name}\n   [{f.rule}] {f.message}"
                      + (f"\n   -> {f.span!r}" if f.span else ""))

    n = len([p for p in args.files if p.exists()]) - skipped
    tail = f", {skipped} unchanged" if skipped else ""
    print(f"\nSummary tics: {n} checked, {failed} failing, "
          f"{warned} with warnings{tail}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
