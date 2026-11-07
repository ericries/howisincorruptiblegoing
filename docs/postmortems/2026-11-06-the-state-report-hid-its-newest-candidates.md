# The state report hid its nine newest candidates, including tonight's pick

**Date:** 2026-11-06
**Found by:** me, during sidebar curation — and only because the "check your own
typing" instruction sent me to list the last nine days of entries by hand. The
report had just told me the newest candidate was dated 2026-10-29. There were
nine newer ones.

## What happened

`scripts/sidebar-state.ts` printed twelve candidate rows, oldest dated
2026-10-29, headed "PASSED OVER — un-featured standalone candidates, by recorded
rail changes since available". Independently enumerating un-featured standalone
entries since 2026-10-01 returned 38. Nine of the missing ones were newer than
anything the report showed:

    2026-11-25  media        incorruptibles-deusto-spanish-edition
    2026-11-05  podcast      wgbt-podcast-outsource-the-work-not-the-thinking
    2026-11-04  endorsement  janice-fraser-clarion-call-and-roadmap
    2026-11-03  endorsement  eric-sillies-book-he-didnt-write
    2026-11-02  endorsement  kathleen-egan-ecomedes-mission-lock
    2026-11-02  endorsement  robert-pasin-radio-flyer-mission-transmission
    2026-11-02  media        thinkers50-london-hundred-copies
    2026-11-01  endorsement  cordell-jacks-regenerative-capital-financial-gravity
    2026-11-01  endorsement  geert-scheipers-strategy-reading-list

Two lines did it, at `scripts/sidebar-state.ts:251-256`:

    .filter((c) => counts[c.id] > 0)
    .sort((a, b) => counts[b.id] - counts[a.id] || ...)
    ...
    for (const c of ranked.slice(0, 12))

A candidate no recorded rail change had yet passed over was dropped outright; of
the rest, a sort by pass-over count descending puts the newest last by
construction, and the slice then cut from that end.

The seventh row is the one that matters. **Thinkers50 London took the slot SOSV
vacated tonight** — Penguin's own commissioning editor reporting that the 100
copies they sent to the Thinkers50 Summit were mostly gone by 10am. It had been
invisible to this job for four consecutive nights.

Measured after the fix, with the old truncation restored as a probe: the report
prints `9 missing` and exits 1. Clean, it exits 0.

## Five whys

**1. Why were nine candidates missing?** A `counts > 0` filter and a
`slice(0, 12)` over a count-descending sort, which together remove exactly the
freshest candidates.

**2. Why was it written that way?** The pass-over count was treated as the
report's product. The script was built to surface entries that a stated objection
had been re-applied to without being re-derived; a candidate at zero pass-overs
has no such story, so it read as noise worth filtering.

**3. Why did that framing survive review?** The postmortem that produced this
script (`2026-10-31-the-sidebar-remembered-in-prose.md`) was about a stale
paragraph — queued picks carried too long, "SOSV is the last event" outliving the
fact. It was built against remembering-too-long. Never-seeing-at-all is the
inverse failure and was not in the case it was built from, so nothing in the
design or its 18 tests pointed at it.

**4. Why was it not caught in six days of use?** Because the omission has no
symptom. The rail stayed full at eight, `INVARIANT ✓` kept passing, and the
composition line kept balancing. A report that silently omits input looks
identical to a report with nothing to say — the only way to see it is to
enumerate the entries yourself, which is the work the report exists to replace.

**5. Why does the system allow that class?** The report asserted its output was
consistent — flags match what index.astro renders — and never asserted its input
was complete. That is the third instance of the same shape in one day: the quote
gate at 2.9% coverage while exiting 0 (2026-10-28), the reshare index that would
have gone on passing if harvestapi renamed a field (fixed this evening), and this.
Consistency checks are cheap to write and coverage checks are the ones that catch
a guard that has stopped looking.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | SOSV rotated out (Eric's session was 11-04, two days past); Thinkers50 London flagged `featured`. Rail verified in the rendered DOM, 8 == 8, highlights floor holds 37 | fix | shipped |
| 2 — the local condition | `rankForReport()` keeps every candidate and sorts newest-first; the pass-over count is printed as an annotation, not used as the sort key — which is what the prompt already says the count is for | test | shipped |
| 3 — the process | Four tests in `tests/sidebar-state.test.ts` pin it: a zero-count candidate is kept, nothing is truncated, order is newest-first and not by count, and ties break on id so the order is stable run to run | test | shipped |
| 4 — why it wasn't caught | The listing heading now states its own population — `CANDIDATES — 21 un-featured standalone entries, newest first` — so the count is on the page instead of implied by what happens to be printed | mechanism | shipped |
| 5 — the system | `candidateReconciliation()` asserts the arithmetic: every standalone entry in the window is on the rail, retired from it, or a candidate, with no fourth bucket. A mismatch prints `CANDIDATE LISTING ✗ … (N missing)` and sets exit 1. Probed by restoring the old `slice(0, 12)`: it reports `9 missing` and exits 1, where the previous report exited 0 and said nothing | structural change | shipped |

## Open items

None. All five rows shipped.

The reconciliation covers rows lost between the entry set and the listing. It
does not cover a candidate wrongly excluded *upstream* of that arithmetic — a bad
`STANDALONE` set, or `excludeRetired` retiring too much. Those would reconcile and
still be wrong. Named here rather than filed as open, because the fix is a
different assertion than this one and no instance of it has occurred.
