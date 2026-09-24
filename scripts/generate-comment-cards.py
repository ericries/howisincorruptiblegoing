#!/usr/bin/env python3
"""Generate share-ready quote cards for the day's best archived LinkedIn comments.

Reads data/archive/linkedin-comments/YYYY-MM-DD.json (or today's file by default),
sorts records by likes desc then confidence, and renders up to N cards to
data/social-cards/YYYY-MM-DD/<slug>.png using the same visual style as the
timeline entry quote cards.

Usage:
  python3 scripts/generate-comment-cards.py                  # today's archive, top 6
  python3 scripts/generate-comment-cards.py 2026-09-15       # specific date
  python3 scripts/generate-comment-cards.py 2026-09-15 10    # top 10 instead of 6
  python3 scripts/generate-comment-cards.py --all            # all records today
"""
import json, re, sys, tempfile
from datetime import date
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts/generate-quote-card.py"
ARCHIVE_DIR = ROOT / "data/archive/linkedin-comments"
OUT_DIR = ROOT / "data/social-cards"


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:maxlen] or "anon"


# Anchor words that let a quote stand alone — must contain at least one.
# Must clearly reference the book/author, not just any pronoun.
_ANCHORS = re.compile(
    r"\b("
    r"incorruptible"                                            # explicit title
    r"|(?:the|this|his|new|latest)\s+book"                      # noun-anchored "book"
    r"|books?\s+(?:of\s+(?:the|our)\s+(?:year|decade|generation|lifetime|century)"  # "books of our generation" etc.
    r"|i(?:'| ha)?ve\s+(?:ever\s+)?read"                        # "books I've read"
    r"|worth\s+reading)"
    r"|(?:reading|re-?listened?\s+to|listened\s+to|finished|devoured)\s+(?:this|it|incorruptible)"  # "reading this", "re-listened to it"
    r"|(?:must|need)[- ]read"                                   # "must-read"
    r"|eric\s+ries|@ericries"                                   # author
    r")\b",
    re.I,
)

# Context-dependent openers — reject if the quote leads with one of these
# UNLESS an anchor appears in the first ~40 chars (e.g. "This book…").
_LEADING_PRONOUN = re.compile(r"^\s*(it|this|these|that|they|them|those|he|she)\b", re.I)

# Emoji stripper (mirror of the renderer's own strip)
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\U00002300-\U000023FF"
    "\U0000FE00-\U0000FE0F\U0000200D\U0000203C\U00002049]"
)


def _normalize(s: str) -> str:
    """Apply cosmetic fixes: em-dash for " - ", strip emoji, collapse spaces."""
    s = _EMOJI.sub("", s)
    # " - " → " — " (em-dash) — matches spaced hyphens used as em-dash surrogates
    s = re.sub(r"\s+-\s+", " — ", s)
    s = re.sub(r"[ \t]{2,}", " ", s).strip()
    return s


def _substantive_text(r: dict) -> str:
    """Best text to use as the quote — pull_quote if the archive computed one,
    otherwise full_text/text trimmed. Normalized (em-dash, emoji-stripped)."""
    q = (r.get("pull_quote") or "").strip()
    if q and len(q) > 20:
        return _normalize(q)
    text = (r.get("full_text") or r.get("text") or "").strip()
    return _normalize(text)


def _passes_selection_gates(r: dict) -> tuple[bool, str]:
    """Returns (ok, reason_if_skipped). Gates per the social-media agent's
    2026-09-15 feedback (data/archive/linkedin-comments/REPLY-3-FROM-POSTER.md).

    1. Respect already_have.
    2. Must have a book anchor (Incorruptible / book / Eric Ries / read it) —
       otherwise the quote can't stand alone on its own image.
    3. Reject leading pronouns UNLESS an anchor appears in the first ~40 chars.
    4. Length floor: 60 substantive chars for regex-matched items; 30 for
       LLM-verified items (short "It's amazing"-class superlatives are
       intentionally kept short — Claude's second-pass classifier already
       vouched for them, and short, sharp cards are highly shareable).
    """
    if r.get("already_have"):
        return False, "already_have"

    q = _substantive_text(r)
    if not q:
        return False, "empty"

    # Length floor — measured after emoji strip / url removal
    substantive = re.sub(r"https?://\S+", "", q).strip()
    is_llm = "<llm>" in (r.get("superlative_matches") or [])
    min_len = 30 if is_llm else 60
    if len(substantive) < min_len:
        return False, f"too-short ({len(substantive)} chars)"

    if not _ANCHORS.search(q):
        return False, "no-book-anchor"

    m = _LEADING_PRONOUN.match(q)
    if m:
        # OK if an anchor lands within the first ~40 chars (e.g. "This book…")
        if not _ANCHORS.search(q[:40]):
            return False, f"leading-pronoun ({m.group(0)!r}) with no early anchor"

    return True, ""


def _rank_key(r: dict):
    """Sort key: high likes first, high-confidence first."""
    likes = int(r.get("likes") or 0)
    low = 1 if r.get("low_confidence") else 0
    return (-likes, low)


def render_card(record: dict, date_str: str, out_dir: Path) -> Path:
    """Render one card by shaping the archive record into the entry schema
    the existing generate-quote-card.py expects, then invoking it."""
    author = record.get("author") or {}
    name = author.get("name") or "Anonymous"
    headline = author.get("headline") or ""
    url = record.get("permalink") or record.get("url") or ""
    quote = _substantive_text(record)

    # Shape into the same schema as a content entry
    entry_id = f"{date_str}-{_slug(name)}"
    shim = {
        "id": entry_id,
        "blockquote": quote,
        "attribution": name,
        "attribution_title": headline,
        "source_url": url,
    }

    # Write a temp entry JSON for the renderer
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(shim, tf)
        tf.flush()
        tmp_path = Path(tf.name)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{entry_id}.png"
    try:
        subprocess.run(
            ["python3", str(GENERATOR), str(tmp_path), str(out_path)],
            check=True, capture_output=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return out_path


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    date_str = args[0] if args and re.match(r"\d{4}-\d{2}-\d{2}", args[0]) else date.today().isoformat()
    top_n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 6
    if "--all" in flags:
        top_n = 10_000

    archive_file = ARCHIVE_DIR / f"{date_str}.json"
    if not archive_file.exists():
        print(f"No archive file for {date_str} at {archive_file}")
        return 1

    all_records = json.loads(archive_file.read_text())
    # Sort first so highest-signal items get priority within the top_n cut
    all_records.sort(key=_rank_key)

    kept, skipped = [], []
    for r in all_records:
        ok, reason = _passes_selection_gates(r)
        if ok:
            kept.append(r)
        else:
            skipped.append((r, reason))

    kept = kept[:top_n]

    out_dir = OUT_DIR / date_str
    print(f"Selection gates: {len(kept)} passed, {len(skipped)} skipped ({len(all_records)} total in archive)")
    if skipped:
        print("Skipped:")
        for r, reason in skipped[:12]:
            au = (r.get("author") or {}).get("name", "?")
            print(f"  ✗ {au:40}  {reason}")

    print(f"\nRendering {len(kept)} card(s) for {date_str} → {out_dir.relative_to(ROOT)}/")
    for r in kept:
        p = render_card(r, date_str, out_dir)
        author = (r.get("author") or {}).get("name", "?")
        likes = r.get("likes", 0) or 0
        low = " [LOW]" if r.get("low_confidence") else ""
        print(f"  ✓ {author:40}  likes={likes:<4}{low}  → {p.name}")

    print(f"\nDone. {len(kept)} card(s) in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
