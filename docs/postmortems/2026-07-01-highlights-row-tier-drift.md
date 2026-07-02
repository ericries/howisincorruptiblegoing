# Highlights row tier drift: why non-household names ended up in the row

**Date:** 2026-07-01
**Reported by:** Eric (asked why "non-prominent people" got added to the row of faces)
**Related:** `docs/postmortems/2026-07-01-highlights-row-text-graphic-fallback.md` (the sibling text-graphic postmortem)

## What happened

Over successive scanner sessions, `type_metadata.highlight` was added to entries for endorsers who don't clear the "household name" bar the row was originally designed for. Concretely, the row picked up **Kathryn Minshew** (The Muse founder), **Tracy Sun** (Poshmark co-founder), **Joel Gascoigne** (Buffer CEO), **Leah Solivan** (TaskRabbit founder), **Vala Afshar** (Salesforce Chief Digital Evangelist), and **Jeff Berman** (Masters of Scale co-host / WaitWhat CEO). All of them are notable in tech — none are household names in the sense of Reid Hoffman / Kim Scott / Adam Grant / Mark Cuban / Dan Heath.

Once the text-graphic fallback fix (sibling postmortem) put faces back in the row, the tier drift became visible in a way it hadn't been before.

## Five Whys

**Why 1** — Why did the agent flag non-household names as `highlight`?
Because the eligibility bar in `memory/feedback_highlights_row.md` — "Reid Hoffman, Kim Scott, Dan Heath, Adam Grant, Seth Godin, Daniel Pink, Mark Cuban, Frances Frei, Bob Sutton, Scott Cook, Ken Chenault, Tim O'Reilly, NBIC, and similar household-name endorsers" — has a soft edge. "And similar" is a judgment call, and successful founders (Buffer CEO, Poshmark co-founder) look "similar" enough in the moment of a scanner cycle where every candidate is credentialed.

**Why 2** — Why does "and similar" get interpreted loosely across sessions?
Because the criterion is subjective and there's no crisp threshold. Different agents (or the same agent in different sessions) draw the line differently. During a scan cycle with many candidates queued, the agent optimizes for "does this person look impressive?" rather than "does this person pass the household-name bar?" Nearly every tech founder in the pipeline looks impressive.

**Why 3** — Why does the agent optimize for "looks impressive?" over the sharper bar?
Because **the default is inclusion** and there's no cost to over-adding. Setting `highlight: "..."` on an entry doesn't produce a red flag on the diff, doesn't fail lint, and looks like a small win in isolation. Each addition passed the "close enough?" test on its own. The dilution only becomes visible in aggregate.

**Why 4** — Why isn't there a cost to over-including?
Because the row was designed to grow monotonically ("never prune" — codified in `feedback_highlights_row_grows.md`), so each individual commit looked like a legitimate append. The append behavior was correct; what was missing was a gate that says "yes, this addition IS a household name — not just any credentialed founder."

**Why 5** — Why is there no gate?
Because the eligibility set lived only in prose. There is no code artifact that enumerates who is on the row. The list is implicit, inferred by pattern-matching against remembered names — which is exactly the mechanism that erodes across sessions.

**Root cause:** The eligibility bar was subjective prose, evaluation was per-entry against an abstract standard, and the default action was "add." Even with lint on `attribution_image` (added in the sibling postmortem), there was no gate on _who_ can enter the row.

## Fix

Codified the eligibility bar as a **hard allowlist** in `scripts/lint-entries.ts`:

```
const HIGHLIGHT_ELIGIBLE_ENDORSERS = new Set([
  // Household names — the launch-era set
  'reid hoffman', 'kim scott', 'dan heath', 'adam grant', 'seth godin',
  'daniel pink', 'mark cuban', 'frances frei', 'bob sutton', 'scott cook',
  'ken chenault', "tim o'reilly", 'matt blumberg', 'jessica jackley',
  // Clearly-peer additions
  'marty cagan',    // SVPG founder, INSPIRED/EMPOWERED/TRANSFORMED
  'steve blank',    // Lean Startup co-creator
  'nir eyal',       // Hooked / Indistractable
  'anil dash',      // long-time tech writer
  'sarah lacy',     // Pando founder, ex-TechCrunch
  'rory sutherland', // Ogilvy vice chairman, Alchemy author, TED
  'jennifer pahlka', // former US Deputy CTO, Recoding America
  'karri saarinen',  // Linear cofounder
])
```

Any entry flagged with `type_metadata.highlight` where `attribution` (lowercased, apostrophe-normalized) is not on the allowlist → lint fails at commit time. Adding a new name requires editing this list — a code change, subject to review — not just setting a flag on an entry.

Pruned entries in this commit (highlight removed, `sidebar_quote` preserved where present):
- Kathryn Minshew, Tracy Sun, Joel Gascoigne, Leah Solivan, Vala Afshar, Jeff Berman.

## Prevention

- **Hard allowlist gate** (this postmortem). No more "and similar" judgment — the set is a code artifact, edited intentionally.
- **Two-tier design:** `sidebar_quote` remains available for legitimate praise from mid-tier endorsers. Those entries still surface on the timeline and can carry a highlighted pull-quote in the sidebar. What they don't get is a face in the row.
- **Default is `sidebar_quote`, not `highlight`.** The scanner instruction is: when you have a strong endorsement quote, use `sidebar_quote`. Only reach for `highlight` if the person is already on the allowlist — otherwise skip it. Adding names to the allowlist is Eric's editorial call, not the scanner's.
