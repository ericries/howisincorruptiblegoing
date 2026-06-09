# 2026-06-09 — Cross-post agent: two structural gaps closed via TDD

## What we observed (first cron iteration)

Ran the daily Buffer cross-post agent end-to-end for the first time using the spec at `docs/buffer-crosspost-guide.md`. Six posts scheduled cleanly via customScheduled — three on Bluesky, three on X, staggered 1–4 days. Verbatim lint passed on every draft (Steve Blank, Steen Thomsen, CNBC).

Two gaps surfaced that the spec assumed but had no tools to satisfy:

1. **No Instagram posts scheduled.** The spec lists Instagram as a target platform, but no asset pipeline exists for IG-safe quote cards. The existing share-card generator produces 1600×900 — wrong aspect for the IG feed, watermark size optimized for desktop preview, not mobile feed.
2. **`cross-posts.json` had no source markers for the historical ~130 LinkedIn-sourced entries.** The agent would silently re-suggest LinkedIn-originated content back to LinkedIn on future runs.

Neither gap is a bug in what the agent *did* today (the 6 posts are good). Both are gaps in what it *can* do on future runs.

## Five whys per gap

### Gap A — No Instagram pipeline

1. **Why no IG posts in this iteration?** No card image generator produces an IG-feed-safe 4:5 portrait card with the watermark visible.
2. **Why doesn't one exist?** The existing `scripts/generate-quote-card.py` produces 1600×900 (16:9). That gets cropped or letterboxed in the IG feed and pushes the watermark off-canvas.
3. **Why was 16:9 chosen originally?** The share card was designed for `og:image` / X share preview / generic share use, all of which prefer wide aspect.
4. **Why wasn't IG designed for at the same time?** IG cross-posting wasn't part of the share-card spec; the cross-post guide added IG as a target later without pairing an asset pipeline to it.
5. **Why was the gap not caught earlier?** No test enforces "every target platform in `PLATFORMS` has an asset pipeline." Each per-platform asset was added ad-hoc; the platform list grew faster than the asset tools.

### Gap B — Source-marker backfill never ran

1. **Why does the agent see only 3 entries in `cross-posts.json`?** Because only the 3 entries scheduled today were added; the file was created blank and no historical-entry backfill existed.
2. **Why does that matter?** Because without `linkedin: "source"` markers on historical LinkedIn-sourced entries, the agent will treat them as eligible LinkedIn targets and re-suggest LinkedIn-originated content back to LinkedIn — a 2:1 balance violation.
3. **Why does the agent rely on those markers instead of inferring from `source_url` at runtime?** The spec is explicit: state file is the source of truth for "already published / originally from." Runtime inference adds work and risks divergence between runs.
4. **Why was the state file shipped empty?** It was assumed daily entries would accumulate markers organically as the agent ran. That assumption fails for a corpus that already has ~130 LinkedIn entries — the originating posts are in the past, not the future.
5. **Why wasn't the inference logic tested against the production entries directory?** No test or CLI exercised `infer_source_markers` against `content/entries/*.json`. The spec said "infer from `source_url`" but the inference function and the entries directory never met before this run.

## What we built (red-green TDD)

### Tool C — shared state library

`scripts/lib/cross_posts.py` (62 lines). Two pure functions:

- `infer_source_markers(entry) -> dict[platform, "source"]` — reads `source_url` and `source_urls[].url`, maps hosts (linkedin.com, x.com / twitter.com, bsky.app, instagram.com) to platform names.
- `merge_state(existing, new) -> dict` — preserves scheduled ISO timestamps over source markers when both exist for the same (entry, platform) cell.

11 tests in `scripts/test_cross_posts.py`. All green.

### Tool B — backfill CLI

`scripts/backfill_cross_posts.py` (50 lines). Walks `content/entries/*.json`, infers markers via Tool C, merges into `data/cross-posts.json` via Tool C. Idempotent.

5 tests in `scripts/test_backfill_cross_posts.py`. Production run on real entries produced:

- 201 entries in state
- 183 LinkedIn source markers
- 20 X source markers
- 1 Bluesky source marker
- All 3 schedules from today's iteration preserved

### Tool A — Instagram card generator

`scripts/generate_ig_card.py`. Adapted from `generate-quote-card.py` for IG-feed-safe 4:5 portrait (1080×1350): cream background, white card, blue rules, Cormorant Garamond italic for the quote, DM Sans for attribution, `howisincorruptiblegoing.com` watermark bottom-right inside the safe area.

6 tests in `scripts/test_generate_ig_card.py`. Structural assertions only — dimensions, file written, watermark area contains rendered pixels. Visual quality (text wrapping, no orphans, balance) stays manual review per the always-Eric-review-the-first-render gate.

## Lessons (locked into tests)

| Test | Lesson |
|---|---|
| `test_render_dimensions_1080x1350` | IG portrait cards must be 1080×1350, not 1600×900. Wide aspect crops in the IG feed. |
| `test_watermark_area_has_rendered_content` | Watermark presence in the bottom strip is a structural invariant — any future refactor that moves it off-canvas fails the test. |
| `test_backfill_idempotent_preserves_schedule` | Backfill must never overwrite a scheduled ISO timestamp with a `"source"` marker. Source < schedule in precedence. |
| `test_scheduled_timestamp_preserved_over_source` (Tool C) | Same invariant at the merge layer, independent of the backfill caller. |
| `test_multiple_platforms_all_marked` | A single entry with `source_url` on platform X and `source_urls[*].url` on platform Y marks both. The agent must avoid re-targeting either platform. |

## What still needs to happen

- **Daily cron**: The cron prompt is saved at `cron-prompts/buffer-crosspost-daily.md`. The harness's `durable:true` flag did not stick in this session — investigate before next session start.
- **IG asset use**: The agent spec needs an update to call `generate_ig_card.py` when a draft targets IG. Spec change is a one-line addition under "Per-platform assets."
- **Postmortem cadence**: This is the third postmortem this week. Pattern is "spec assumed a tool that didn't exist." Next time the spec lists a new target platform or state file, the same iteration must produce the matching pipeline + test.
