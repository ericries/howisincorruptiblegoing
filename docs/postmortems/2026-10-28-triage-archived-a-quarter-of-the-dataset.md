# The triage script archived 60 of 246 items and reported success

**Date:** 2026-10-28
**Found by:** A billing lookup, by accident. I pulled the Apify run record to
understand a *different* number and noticed it had charged for 50 posts and 196
comments while the archive file I had just written held 13 posts and 47 comments.
Nothing in the repo would have told me. This is the second postmortem of the day;
the first is [`2026-10-28-item-cap-starved-the-post-feed.md`](2026-10-28-item-cap-starved-the-post-feed.md),
and this bug was found while verifying that one's fix.

## What happened

Re-pulling Eric's author feed with the corrected caps, `scan-triage.py --archive`
printed `archived 60 items` and exited 0. The dataset held 246.

```
dataset kwhFcvMlIDosemyFu:  itemCount 246,  readCount 60
run     t1H2hFeZNhhfeDAPz:  SUCCEEDED, 65.8s, charged 50 posts + 196 comments
```

The run took 65 seconds to write. The script polled once, about a second in,
read the 60 rows that existed so far, and returned — because its stopping
condition was `len(items) >= expect`, with `expect` defaulting to 1.

Read fully, the same dataset gives 50 posts spanning 2026-10-22 to 2026-10-28,
including both days the first postmortem was about. Read as archived, it gives
13 posts spanning two days — which is exactly the shape of the bug I was
investigating, and I nearly concluded the cap fix had failed.

A second finding fell out of the same run record: Apify applies a **default
`maxTotalChargeUsd` of $0.50** that nobody set (`isMaxTotalChargeUsdSetByUser:
false`). The recovery pull cost **$0.49205**. A normal week finished $0.008
under an invisible ceiling, and a busier one would have truncated against it
silently — the identical failure to the one the first postmortem documents, one
layer down. It is now set explicitly to $1.50.

## Five whys

**1. Why did the archive file hold 60 of 246 items?**
`fetch()` returned on its first poll, roughly a second into a 65-second run,
because 60 ≥ 1 satisfied its stopping condition.

**2. Why does a successful read stop at "some items exist"?**
`expect` was built as a latency floor for the `waitSecs: 0` pattern — "don't
block, just tell me when there's something" — and nothing ever distinguished
"the dataset has rows" from "the dataset is finished". The default of 1 made
every call ask the weakest possible question.

**3. Why was completeness never part of the stopping condition?**
`itemCount` is one field on the dataset metadata endpoint and was never
requested. The script's design note is explicit that it exists to avoid Apify
MCP round-trips, which cost 5.34M of 7.73M tokens in a measured session. That
optimisation was real, but it priced only tokens. The cost of reading a
half-written dataset was never on the ledger, so a second cheap HTTP call looked
like a regression rather than a correctness requirement.

**4. Why did this survive undetected in every scan that used it?**
Because a short archive is indistinguishable from a quiet day. There is no
record of what the dataset *should* have held, so nothing could disagree. The
one check that reads these files — `feed_coverage`, written four hours ago —
would have reported the resulting hole as a scraping gap and sent me to raise a
cap that was never binding. A detector reading corrupted input confidently
reports the wrong cause.

**5. Why does the system treat a response as the data?**
Every fetch in this repo stops at "the request succeeded". None compares what
came back against what was asked for. That is the same shape as the first
postmortem — a limit bound quietly and nothing checked the result against the
intent — and it is the default failure mode of every polled or paginated API
here, including the `maxTotalChargeUsd` default found in the same run record.
The boundary where external data enters the repo had no completeness assertion
anywhere on it.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | Re-archived `2026-10-28-recovery-author.json` at full 246 items / 50 posts, spanning 10-22..10-28 | fix | shipped |
| 2 — the local condition | `fetch()` default `expect` 1 → 0, so the floor no longer answers a question it was never asked; completeness alone decides when to stop | fix | shipped |
| 3 — the process | `fetch()` polls until the read matches the dataset's own `itemCount`, read *after* the items so concurrent writes surface as `count > n_read` rather than being missed. 13 tests in `scripts/test_scan_triage_fetch.py` pin the contract, including the exact 60-of-246 shape | test | shipped |
| 4 — why it wasn't caught | `archive()` refuses to overwrite a fuller file with a shorter one and prints `WARNING: partial read (N of M)` to stderr. A partial read can no longer destroy the record it disagrees with, and can no longer pass silently | mechanism | shipped |
| 5 — the system | Completeness is now asserted at the boundary rather than assumed: `is_complete()` is a named, tested predicate that both the fetch loop and the archive writer go through, so there is one place to extend when another source is added. The sibling instance of the same class — the unset `maxTotalChargeUsd` default — was found by this chain and closed in `docs/CRONS.md`: every cap that governs these calls is now set explicitly rather than inherited, because an invisible default is still a cap | structural change | shipped |

## Open items

`fetch()` is the only reader hardened so far. Other code paths in the repo pull
remote data and stop at "the request succeeded" — the Goodreads and Amazon
lanes among them. Nothing is known to be broken there, and auditing them was out
of scope for a fix made while verifying a different fix, so this is **open**
rather than declined. The level-5 mechanism was built as a shared predicate
specifically so that audit is cheap when it happens.
