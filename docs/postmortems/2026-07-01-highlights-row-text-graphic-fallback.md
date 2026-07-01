# Highlights row diluted with text-graphics and non-prominent people

**Date:** 2026-07-01
**Reported by:** Eric (screenshot showing text-graphic tiles instead of faces in the top row of the home page)

## What happened

Of 28 entries with `type_metadata.highlight`, 11 had `attribution_image: null`. `src/components/Highlights.astro` falls back to `entry.image` when `attribution_image` is missing — and `entry.image` for endorsement/review/media entries is now the auto-generated **quote card** (styled text on a colored background) produced by `scripts/backfill-quote-cards.py`. Result: 11 of the 28 highlights rendered as text tiles rather than faces, and the row visibly stopped looking like a row of faces.

Separately, several entries flagged with `highlight` sit at mid-tier prominence (Kathryn Minshew, Tracy Sun, Joel Gascoigne, Leah Solivan, Vala Afshar, Jeff Berman) rather than the household-name tier documented in `memory/feedback_highlights_row.md`. Once the row lost its face-only visual signature, the tier drift became obvious.

## Five Whys

**Why 1** — Why are text graphics appearing in the highlights row?
Because `Highlights.astro` line 48 falls back to `entry.image` when `attribution_image` is null, and `entry.image` is now the quote card (a text graphic) for any endorsement/review/media entry that ran through `backfill-quote-cards.py`.

**Why 2** — Why do so many highlight entries have `attribution_image: null`?
Because at ship time the scanner sets `highlight` but doesn't download a face image. `backfill-quote-cards.py` fills `entry.image` with a text card, which silently "works" as a fallback in `Highlights.astro` even though it violates the design intent.

**Why 3** — Why did the fallback stay silent?
Because the invariant "`highlight` requires a real face image" was documented only in `memory/feedback_highlights_row.md` — soft guidance for a scanner agent, not a hard gate. `scripts/lint-entries.ts` enforces `HIGHLIGHTS_FLOOR` (count can't drop) but has no per-entry integrity check that the image is actually a face.

**Why 4** — Why is that invariant only in memory?
Because when the pattern was first set up, the highlighted entries all had faces by chance (they were curated big names shipped by hand). The fallback path in `Highlights.astro` existed as a defensive `|| null` and was never exercised in practice. The moment the scanner started auto-flagging highlights without a photo-fetch step, the previously-latent fallback started firing on every new entry.

**Why 5** — Why did the scanner start auto-flagging highlights without checking for a photo?
Because "add highlight to any big-name endorser" was pattern-matched to the highlight *flag*, but the accompanying obligation to add an `attribution_image` was only in a memory paragraph. Advisory-only rules erode; only lint gates hold.

**Root cause:** Invariants that matter to the visual product must be enforced by lint, not by memory. `highlight` without a real face is a lint-fail-worthy state, not a memory-note-worthy state.

## Blast radius

- 11 of 28 highlight tiles rendered as text cards, visibly degrading the top-of-page row of faces
- Some of those 11 were also mid-tier prominence — the tier-drift was masked as long as the text tiles all looked equivalent

## Fix

1. **RED test:** add a lint rule in `scripts/lint-entries.ts` — for every entry with `type_metadata.highlight`, `attribution_image` must be non-null AND must not start with `/images/cards/` (the quote-card directory), AND the referenced file must exist on disk.
2. **GREEN:** download real headshots for the 11 missing entries and wire `attribution_image` to `/images/people/{slug}.jpg`.
3. **Memory update:** `feedback_highlights_row.md` now names the lint rule explicitly. The scanner instruction is "no `highlight` without a real face on disk; lint will fail otherwise."

## Prevention

- **Lint gate** (this postmortem): shipped in `scripts/lint-entries.ts`.
- **Scanner workflow update:** when adding a highlight flag, download the endorser's photo to `public/images/people/{slug}.jpg` in the same commit. If a photo can't be sourced, don't set `highlight` — set only `sidebar_quote` (which has no face requirement) or leave to Eric to add manually.
- **Tier gate:** memory `feedback_highlights_row.md` continues to list eligible household-name endorsers. Non-household mid-tier names get `sidebar_quote` or `featured`, not `highlight`.
