#!/usr/bin/env python3
"""
Backfill local transcript archive for every shipped entry with a YouTube URL.

The archive lives in data/archive/transcripts/<entry-id>.txt and is gitignored —
this is for local re-grep only, never deployed to the site.

Idempotent: skips entries whose transcript file already exists. Run any time.
"""
import json
import glob
import re
import sys
from pathlib import Path

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
except ImportError:
    sys.stderr.write("Install youtube-transcript-api first: pip install youtube-transcript-api\n")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "content" / "entries"
ARCHIVE = ROOT / "data" / "archive" / "transcripts"
ARCHIVE.mkdir(parents=True, exist_ok=True)

VID_RE = re.compile(r"youtube\.com/watch\?v=([\w-]{11})|youtu\.be/([\w-]{11})")


def extract_vid(url):
    if not url:
        return None
    m = VID_RE.search(url)
    return m.group(1) or m.group(2) if m else None


def fetch_transcript(vid):
    """Try fetching English transcript first, fall back to any available language."""
    api = YouTubeTranscriptApi()
    try:
        segments = api.fetch(vid, languages=["en"])
    except Exception:
        try:
            segments = api.fetch(vid)
        except Exception as e:
            return None, str(e)
    text = " ".join(s.text for s in segments)
    return text, None


def main():
    fetched = 0
    skipped = 0
    failed = 0
    failures = []
    for path in sorted(ENTRIES.glob("*.json")):
        try:
            d = json.loads(path.read_text())
        except Exception:
            continue
        entry_id = d.get("id") or path.stem
        out = ARCHIVE / f"{entry_id}.txt"
        if out.exists():
            skipped += 1
            continue
        vid = None
        for url in [d.get("source_url"), d.get("video_url")]:
            vid = extract_vid(url)
            if vid:
                break
        if not vid:
            continue
        text, err = fetch_transcript(vid)
        if text is None:
            failed += 1
            failures.append((entry_id, vid, err[:120] if err else "unknown"))
            continue
        out.write_text(text)
        fetched += 1
        print(f"  ✓ {entry_id} ({len(text):,} chars)")
    print(f"\nFetched {fetched}; skipped (already cached) {skipped}; failed {failed}")
    if failures:
        print("\nFailures:")
        for entry_id, vid, err in failures:
            print(f"  ✗ {entry_id}  vid={vid}  {err}")


if __name__ == "__main__":
    main()
