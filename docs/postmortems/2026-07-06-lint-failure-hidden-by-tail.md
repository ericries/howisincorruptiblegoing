# 2026-07-06 — Lint failure hidden by `tail -N`

## What happened

During the Goodreads scan, I wrote two new review entries with
`scanner_source: "goodreads-scan"`. The pre-commit hook rejected the
commit twice with:

```
"scanner_source" must be one of [web-search, social-scan, manual, rss], got "goodreads-scan"
```

Not a schema surprise on its own — but I ran `npx tsx scripts/lint-entries.ts 2>&1 | tail -5`
right after writing the entries and saw only ✓ lines. I assumed lint had
passed and moved to commit; the hook re-ran lint end-to-end and surfaced
the FAIL that the CLI had printed *inline*, mid-loop, alphabetically in
the middle of the file list. `tail -5` never saw it.

## Five whys

1. **Why did the commit fail after `lint-entries.ts` printed all ✓?**
   Because `tail -5` sliced the last 5 lines of the piped output. The
   failing file (`2026-07-01-rob-moore…`) was alphabetically in the
   middle, so its `❌` line was printed early and dropped by tail.
2. **Why did I trust a tail slice?**
   Habit. Lint output is long; I default to trimming. But without a
   trailing summary, tail is a broken proxy for "did it pass?"
3. **Why does `lint-entries.ts` interleave FAILs mid-loop with no trailing
   summary?**
   Legacy design — the CLI printed `✓ file.json` or `❌ file.json` per
   file and exited. No post-loop summary line.
4. **Why did I use `goodreads-scan` in the first place — beyond the
   tail-truncation issue?**
   The Goodreads cron prompt calls itself "Goodreads review scan," so I
   extrapolated `scanner_source: "goodreads-scan"`. Nothing in the prompt
   or in memory told me the enum was `[web-search, social-scan, manual, rss]`.
5. **Why isn't the allowed enum documented in the cron prompt?**
   Nobody put it there. The enum lives only in the schema
   (`src/lib/schema.ts`). The cron prompts don't mention `scanner_source`
   at all.

## Root causes (two)

- **Observability:** `lint-entries.ts` had no trailing summary. `tail -N`
  on the piped output silently hid mid-loop failures.
- **Discoverability:** the `scanner_source` enum wasn't surfaced in the
  Goodreads cron prompt where a new scanner_source string was being
  invented.

## Fixes (red/green TDD)

### 1. Trailing summary that `tail -N` cannot hide

Added `formatLintSummary(failures)` to `scripts/lint-entries.ts` and
wired the CLI to accumulate failures instead of only printing them
inline. At the end of every run the CLI now prints one of:

```
Lint: OK — all entries valid.
```

or

```
Lint: N failure(s):
❌ file.json
   - specific error
```

`tail -5` on a failing run now always shows the failure summary.

Tests in `tests/lint-entries.test.ts`:

- `formatLintSummary` returns `"Lint: OK"` for zero failures
- `formatLintSummary` names every failing file in the trailing block
- The failure block is at the tail of the output (survives `slice(-5)`)

All three failed before the implementation change and pass after (RED → GREEN).

### 2. Cron prompt discoverability

Updated `memory/project_scanner_crons.md` Goodreads cron entry to name
the canonical value explicitly:

> Set `scanner_source: "social-scan"` (the schema only permits
> `[web-search, social-scan, manual, rss]` — "goodreads-scan" is NOT
> valid and will fail the pre-commit lint).

## Prevention checklist

- Never trust `tail -N | grep -v ✓` as "did lint pass." Read the trailing
  summary line. It now exists.
- When a cron prompt has a name pattern that doesn't match a schema
  enum, spell out the enum value in the prompt.
- If a similar Symbol-vs-Concept mismatch bites in a future scan,
  document the canonical value in the same commit that fixes the entry.
