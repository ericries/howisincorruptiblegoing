"""Verify blockquotes against the source text already captured on disk.

    python3 scripts/quote_integrity.py              # every entry, with coverage
    python3 scripts/quote_integrity.py <file.json>  # just these entries

No network. Costs nothing. Checks the entries a fetch provably cannot.

Why this exists, measured 2026-10-28:

    verify-quotes.ts        verified   25 of 871 entries (2.9%) and exited 0
    review_bot/verify_quotes.py   passes any entry whose URL it cannot fetch

The first skipped every entry with `verified: false`; nothing has set that
field true since June 2026, so the skip swallowed 725 entries. The second has
no such skip but treats a failed fetch as a pass, and 62% of entries cite
LinkedIn or X, which no anonymous fetch can read.

Both were re-acquiring evidence the repo already holds. The scanner saves the
entire post or review to `data/archive/source-texts/<entry-id>.json` — 263
entries, 156 of them behind auth walls. That is the corpus to check against.

The verdicts are deliberately four-valued. "I could not check this" must never
collapse into "this is fine", which is the bug that made both old verifiers
report success while verifying nothing.
"""

from __future__ import annotations

import argparse
import enum
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRIES = REPO / "content" / "entries"
SOURCE_TEXTS = REPO / "data" / "archive" / "source-texts"

# How much of a quote's opening must appear for "the start matches but the whole
# does not" to be worth reporting as PARTIAL rather than ABSENT. Below this the
# fragment is too short for a prefix hit to mean anything — "astounding" appears
# inside plenty of unrelated prose.
PARTIAL_WINDOW = 40


class Verdict(enum.Enum):
    """Four outcomes, because three of them are not "pass"."""

    EXACT = "exact"            # byte-for-byte present
    NORMALISED = "normalised"  # present once quotes/dashes/spacing are folded
    PARTIAL = "partial"        # opening present, whole quote is not — composite risk
    ABSENT = "absent"          # not there at all
    NO_SOURCE = "no-source"    # nothing captured to check against
    SOURCE_MISMATCH = "source-mismatch"  # capture is of a different document
    MEDIUM_MISMATCH = "medium-mismatch"  # capture is audio; quote may be page copy
    WEAK_CAPTURE = "weak-capture"  # backfilled HTML scrape; may be only page chrome
    COMMENT_MISMATCH = "comment-mismatch"  # capture is the post; quote is a reply to it

    @property
    def is_failure(self) -> bool:
        return self in (Verdict.PARTIAL, Verdict.ABSENT)

    @property
    def was_checked(self) -> bool:
        """A quote proven wrong IS verified — the strongest kind of verification.

        SOURCE_MISMATCH is not checked: the capture is of a different document,
        so it can neither confirm nor refute. Counting it as checked would let
        coverage drift upward on evidence that proves nothing.
        """
        return self not in (Verdict.NO_SOURCE, Verdict.SOURCE_MISMATCH,
                            Verdict.MEDIUM_MISMATCH, Verdict.WEAK_CAPTURE,
                            Verdict.COMMENT_MISMATCH)


def normalise(text: str) -> str:
    """Fold the differences that are typographic rather than substantive."""
    text = text.lower()
    text = re.sub(r"[‘’‛]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = text.replace("—", "--").replace("–", "-")
    text = text.replace("…", "...").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


# A cut is marked by an ellipsis with space on BOTH sides. Authors write "..."
# mid-sentence to trail off — Brandon Fong's post has "...and why success
# itself" inside one clause — and treating that as a cut would split a
# contiguous quote and then fail to find the halves.
_CUT_RE = re.compile(r"\s+(?:…|\.\.\.)\s+")


def _match_segmented(quote: str, source_text: str) -> Verdict | None:
    """Verify an "A … B" quote segment by segment, in source order.

    `repair_elisions` rewrites a silently-cut quote into this form, which is
    the honest one. If the checker could not read it, repairing a composited
    quote would make the entry fail forever — the fix would look like the bug.
    """
    parts = [p.strip() for p in _CUT_RE.split(quote) if p.strip()]
    if len(parts) < 2:
        return None

    for text, verdict in ((source_text, Verdict.EXACT),
                          (normalise(source_text), Verdict.NORMALISED)):
        pos = -1
        ok = True
        for part in parts:
            needle = part if verdict is Verdict.EXACT else normalise(part)
            i = text.find(needle, pos + 1)
            if i <= pos:
                ok = False
                break
            pos = i
        if ok:
            return verdict
    return Verdict.ABSENT


def match_quote(quote: str, source_text: str) -> Verdict:
    """How well does `quote` appear in `source_text`?

    EXACT is reported only on a raw substring hit. A quote that matches only
    after normalisation has drifted from the source at the byte level — usually
    because it was retyped rather than copied — and Eric has asked specifically
    that apostrophe and dash types match. That is worth seeing, so it gets its
    own verdict rather than being folded into a pass.
    """
    if not quote or not source_text:
        return Verdict.NO_SOURCE

    if quote in source_text:
        return Verdict.EXACT

    segmented = _match_segmented(quote, source_text)
    if segmented is not None:
        return segmented

    nq, ns = normalise(quote), normalise(source_text)
    if not nq or not ns:
        return Verdict.NO_SOURCE
    if nq in ns:
        return Verdict.NORMALISED

    # The composited-quote signature: the quote opens with real source text and
    # then continues into something the source never said. A quote too short for
    # the window cannot produce a meaningful prefix hit, so it stays ABSENT.
    if len(nq) > PARTIAL_WINDOW and nq[:PARTIAL_WINDOW] in ns:
        return Verdict.PARTIAL

    return Verdict.ABSENT


class Result:
    __slots__ = ("entry_id", "verdict", "quote", "source_url")

    def __init__(self, entry_id: str, verdict: Verdict, quote: str = "",
                 source_url: str = ""):
        self.entry_id = entry_id
        self.verdict = verdict
        self.quote = quote
        self.source_url = source_url

    def __repr__(self) -> str:
        return f"Result({self.entry_id!r}, {self.verdict.value})"


def load_source_text(entry_id: str, archive_dir: Path = SOURCE_TEXTS) -> str | None:
    """The captured full text for an entry, or None if we never saved one."""
    f = Path(archive_dir) / f"{entry_id}.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text()).get("full_text") or None
    except (json.JSONDecodeError, OSError):
        # A corrupt capture is missing evidence, not contradicting evidence.
        return None


def _url_key(u: str | None) -> str:
    """Scheme/www/trailing-slash-insensitive url identity."""
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u.strip())
    u = re.sub(r"^www\.", "", u)
    return u.split("#")[0].rstrip("/").lower()


def load_capture(entry_id: str, archive_dir: Path = SOURCE_TEXTS) -> dict | None:
    """The whole capture record, so its url can be compared as well as its text."""
    f = Path(archive_dir) / f"{entry_id}.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return None


_HANDLE_RE = re.compile(r"linkedin\.com/posts/([^_/]+)_")


def _quotes_a_comment(entry: dict) -> bool:
    """Is the quoted person someone other than the author of the cited post?

    A LinkedIn post capture contains the post body and not its replies, so when
    an entry attributes the quote to anyone but the post's author, the words are
    almost certainly a comment and the capture cannot speak to them. The author
    is recoverable from the url slug: /posts/<handle>_...

    Compared on letters only, because handles drop spaces and add digits —
    "bobsutton1" is "Bob Sutton".
    """
    m = _HANDLE_RE.search(entry.get("source_url") or "")
    attribution = entry.get("attribution") or ""
    if not m or not attribution:
        return False
    handle = re.sub(r"[^a-z]", "", m.group(1).lower())
    tokens = [re.sub(r"[^a-z]", "", t.lower()) for t in attribution.split()]
    tokens = [t for t in tokens if t]
    name = "".join(tokens)
    if not handle or not name:
        return False
    if handle in name or name in handle:
        return False
    # Handles routinely compress the first name to an initial: "eries" is Eric
    # Ries, "bobsutton1" is Bob Sutton. A surname of four or more letters
    # appearing in the handle is a match; shorter ones match too much to trust.
    surname = tokens[-1]
    if len(surname) >= 4 and surname in handle:
        return False
    return True


def check_entry(entry: dict, archive_dir: Path = SOURCE_TEXTS) -> Result:
    """Verify one entry against its capture.

    A miss only refutes the quote when the capture is of the document the entry
    actually cites. The archive is keyed by entry id but sometimes holds a
    RELATED url — the X post announcing an article rather than the article, a
    reaction comment rather than the post it replies to. Running the checker for
    the first time produced 83 "failures", and the two I opened were both this:
    sound entries judged against the wrong document.

    A hit, by contrast, counts wherever it is found. If the words are provably
    in a captured document they are real words, and the url bookkeeping does not
    make them less real.
    """
    entry_id = entry.get("id", "")
    quote = entry.get("blockquote") or ""
    cap = load_capture(entry_id, archive_dir)
    text = (cap or {}).get("full_text") or ""

    if not text:
        return Result(entry_id, Verdict.NO_SOURCE, quote, entry.get("source_url", ""))

    verdict = match_quote(quote, text)
    if verdict.is_failure:
        cap_url, entry_url = _url_key(cap.get("source_url")), _url_key(entry.get("source_url"))
        # An absent source_url on the capture predates the field; compare anyway
        # rather than letting "unknown" excuse a miss on the only evidence held.
        if cap_url and entry_url and cap_url != entry_url:
            verdict = Verdict.SOURCE_MISMATCH
        elif cap.get("platform") == "linkedin" and _quotes_a_comment(entry):
            verdict = Verdict.COMMENT_MISMATCH
        elif cap.get("evidence") == "weak":
            # A backfilled HTML scrape frequently contains only nav and
            # headline: Goodreads, Fortune and a podcast page each yielded
            # 2-10KB of chrome with no body and convicted a sound entry. We
            # cannot separate "the entry is wrong" from "we only got the
            # chrome", so weak evidence does not get to convict. A url-keyed
            # API capture is not weak and its misses are real findings.
            verdict = Verdict.WEAK_CAPTURE
        elif cap.get("platform") == "transcript":
            # One url, two bodies of text: the spoken audio and the written
            # show notes. We capture the audio; blockquotes are often pulled
            # from the blurb. A transcript can confirm a quote but never refute
            # one, because the document that would hold it was never captured.
            verdict = Verdict.MEDIUM_MISMATCH
    return Result(entry_id, verdict, quote, entry.get("source_url", ""))


# Entries allowed to ship with no captured source text, each with a stated
# reason. Deliberately a committed file rather than a field on the entry: a
# field flip is what `verified: false` was, and it ended up on 725 entries
# because an error message named it. A waiver here is reviewable and countable.
WAIVERS = REPO / "data" / "no-capture-waivers.json"


def load_waivers(path: Path = WAIVERS) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def missing_capture(entries: list[dict], archive_dir: Path = SOURCE_TEXTS,
                    allowed: dict | None = None) -> list[str]:
    """Entry ids that carry a blockquote but no evidence anyone could check.

    708 entries are in this state, every one of them shippable because the
    capture was optional. Fixing the checker cannot help an entry whose source
    text was never saved, so the requirement belongs at ship time.

    A waiver needs a non-empty reason. An empty one is a field flip wearing a
    file's clothes.
    """
    allowed = load_waivers() if allowed is None else allowed
    out = []
    for e in entries:
        eid = e.get("id", "")
        if not (e.get("blockquote") or "").strip():
            continue
        if str(allowed.get(eid, "")).strip():
            continue
        if load_source_text(eid, archive_dir):
            continue
        out.append(eid)
    return out


def coverage(verdicts: list[Verdict]) -> dict:
    """How much of the corpus this run actually checked.

    Reported every run, because the failure being guarded against here is not a
    bad quote — it is the checker quietly checking nothing while exiting 0.
    """
    total = len(verdicts)
    checked = sum(1 for v in verdicts if v.was_checked)
    return {
        "total": total,
        "checked": checked,
        "unverifiable": total - checked,
        "failures": sum(1 for v in verdicts if v.is_failure),
        "exact": sum(1 for v in verdicts if v is Verdict.EXACT),
        "normalised": sum(1 for v in verdicts if v is Verdict.NORMALISED),
        "fraction": (checked / total) if total else 0.0,
    }


# --- CLI ------------------------------------------------------------------------------

def _load_entries(paths: list[str]) -> list[dict]:
    files = [Path(p) for p in paths] if paths else sorted(ENTRIES.glob("*.json"))
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError) as ex:
            print(f"  could not read {f}: {ex}", file=sys.stderr)
    return out


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="entry JSON files (default: all)")
    ap.add_argument("--min-checked", type=int, default=0,
                    help="fail if fewer than N entries could be checked")
    ap.add_argument("--quiet", action="store_true", help="only show problems")
    ap.add_argument("--require-capture", action="store_true",
                    help="fail if a listed entry has no captured source text")
    args = ap.parse_args()

    results = [check_entry(e) for e in _load_entries(args.files)]
    c = coverage([r.verdict for r in results])

    for r in results:
        if r.verdict.is_failure:
            print(f"❌ {r.entry_id} — quote {r.verdict.value.upper()} in captured source")
            print(f"   {r.quote[:110]}")
            print(f"   {r.source_url}")
        elif r.verdict is Verdict.NORMALISED and not args.quiet:
            print(f"⚠️  {r.entry_id} — matches only after normalising "
                  f"(apostrophe/dash/spacing drift)")

    print(f"\nQuote integrity: checked {c['checked']}/{c['total']} entries "
          f"({c['fraction']:.1%}) against captured source text")
    print(f"  exact {c['exact']}  normalised {c['normalised']}  "
          f"failures {c['failures']}  no capture {c['unverifiable']}")

    if args.require_capture:
        entries = _load_entries(args.files)
        gaps = missing_capture(entries)
        if gaps:
            print(f"\nFAIL: {len(gaps)} entry(ies) have a blockquote but no captured "
                  f"source text, so nothing can ever verify them:", file=sys.stderr)
            for g in gaps:
                print(f"  {g}", file=sys.stderr)
            print("\nSave the full source to data/archive/source-texts/<id>.json "
                  "as {\"entry_id\", \"source_url\", \"platform\", \"full_text\"}.\n"
                  "If the source genuinely cannot be captured, add the id to "
                  "data/no-capture-waivers.json WITH A REASON.", file=sys.stderr)
            return 1

    if c["checked"] < args.min_checked:
        print(f"\nFAIL: only {c['checked']} entries could be checked, "
              f"floor is {args.min_checked}. Coverage has gone backwards — a "
              f"checker that checks nothing still exits 0, which is the bug "
              f"this floor exists to catch.", file=sys.stderr)
        return 1
    return 1 if c["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(_main())
