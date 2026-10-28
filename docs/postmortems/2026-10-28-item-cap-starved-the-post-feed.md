# A cost cap justified by a miscount silently starved the post feed of two days' coverage

**Date:** 2026-10-28
**Found by:** Eric asked for five whys after I reported the second hole in two
runs and proposed a fix. I had already found both holes — but late, by hand, and
only after they were unrecoverable, and on the first one I absorbed it instead of
investigating. The finding is that the diagnosis only happened because he asked.

## What happened

The LinkedIn comment-archive job (Mon/Wed/Fri 10:47) pulls Eric's author feed and
an `Incorruptible Ries` keyword search from `harvestapi/linkedin-post-search` with
comments enabled. On 2026-10-28 the author pull returned 39 items covering a single
day, 2026-10-28. The previous run, on 10-26, had reached back only to 10-26.
**2026-10-27's posts and their comments were never scanned by this lane.** The same
shape had happened three days earlier: the 10-26 run reached to 10-25, the 10-23 run
reached to 10-23, so **2026-10-24 was also never covered.**

Both times the job fired on schedule and wrote its watermark, so
`scan_catchup.py` reported "nothing overdue" — correctly.

Measured, not inferred:

| run | items | posts | comments | post range |
|---|---|---|---|---|
| 2026-10-01 (pre-cap) | 123 | **30** | 93 | 09-28 .. 10-01 |
| 2026-10-14 (pre-cap) | 130 | **30** | 100 | 10-12 .. 10-14 |
| 2026-10-26 (capped) | 40 | 11 | 29 | 10-25 .. 10-26 |
| 2026-10-28 (capped) | 39 | **6** | 33 | 10-28 .. 10-28 |

The dataset is a single interleaved stream. Printing item kinds in order for
2026-10-28 gives `cPccccccccccPcPccccPcccccccccccccccPcPc` — a post, then its
comments, then the next post. `callOptions.maxItems` truncates that stream by
total item count, so comments on early posts consume the budget later posts
needed. A cap of 40 reached the 6th post of a requested 30.

Pricing, from the actor's own schema: `$0.002` per item at our tier, **identical
for a post and a comment**. Month-to-date Apify spend on 2026-10-28 was **$19.46
of $29**, and the recent daily burn was $0.28 (the month total is inflated by a
one-off $6.27 on 10-03). The 40-item cap across both calls was saving roughly
**$5/month** on a budget with more than $10 of slack.

## Five whys

**1. Why was 2026-10-27 never scanned?**
The 10-28 author pull covered only 10-28, and the previous pull stopped at 10-26.
Neither touched the 27th.

**2. Why did the pull cover one day when `postedLimit` was `"week"` and `maxPosts` was 30?**
It returned 6 posts, not 30. `callOptions.maxItems: 40` truncated the interleaved
post/comment stream at 39 items; 33 of those were comments. `postedLimit` and
`maxPosts` were both honoured — they simply never got the chance to matter,
because the total-item cap bound first.

**3. Why was a total-item cap used on a call whose items are two different kinds with different purposes?**
Because the cost-control decision on 2026-10-14 rested on a miscount. The note
written into `docs/CRONS.md` that day read: *"maxPosts is NOT honoured by the
actor (30 was passed, 130 returned)."* That 130-item pull was **30 posts and 100
comments** — `maxPosts: 30` was obeyed exactly. The unbounded dimension was
comments, which at `maxComments: 30` across 30 posts could reach 900 items and
was never capped at all. Believing the per-dimension knob was ignored, a total
cap looked like the only available lever. It was aimed at a problem that did not
exist and it hit the one thing that mattered.

**4. Why did 14 days pass with the cap starving the feed and nothing noticing?**
Nothing measured it. `scan_catchup` answers "did the job run" and answered
correctly both times. The only coverage check that existed was a prose
instruction in the prompt — *"Compare the oldest post in this pull against the
newest in the previous run's archive file"* — which is a by-hand comparison. It
did find both holes, which is why they are in the record at all, but it can only
ever find a hole after it exists and is unrecoverable, never the starvation that
predicts one. And on the first hole I reported it and moved on, exactly as the
prompt's own guidance allowed ("a one-day gap is usually not worth extra spend").

**5. Why does the system let a cost control silently degrade a result for two weeks?**
Because the control lived only as prose in a cron prompt. Nothing in the
repository could read the number, so nothing could check what it was doing — not
a test, not a lint, not the catch-up script. And the claim that justified it was
written into the same prompt as settled fact, where it was re-read as evidence
by every later run, including by me when I inherited it. A measurement nobody can
re-run becomes an assumption; an assumption in a prompt becomes policy. The
2026-10-21 postmortem named this exact pattern for watchdog re-syncs and the
mechanism it produced did not generalise past that one case.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | Re-pull the author feed with `postedLimit: "week"` and dedup against `data/archive/linkedin-comments/`, recovering 10-27 and 10-24 | fix | shipped |
| 2 — the local condition | `maxItems` 40 → 250 and `maxPosts` 30 → 50 on both calls in `docs/CRONS.md`; cap each dimension at its own knob and leave `maxItems` as a backstop clear of normal volume. 30 posts reached back only ~4 days against a 3-day Fri→Mon gap — that margin was the entire safety factor and was never stated | fix | shipped |
| 3 — the process | `scripts/feed_coverage.py`: `find_holes` compares consecutive pulls per lane, `is_starved` flags a pull that hit the cap short of its post quota. 21 tests, including a regression asserting the 10-14 dataset holds exactly 30 posts — so the miscount that caused this cannot be made again silently | test | shipped |
| 4 — why it wasn't caught | `feed_coverage.report()` wired into `scan_catchup._main()`, which already runs free and local at every session start and whose output I am required to read. It prints HOLE and STARVED unprompted. The prose "compare the oldest post" instruction is deleted and replaced by the script call | mechanism | shipped |
| 5 — the system | The cap is no longer prose only: it lives in `feed_coverage.LANE_REQUEST`, and `test_lane_request_matches_the_caps_in_crons_md` pins the two together so a future cap change cannot disarm the detector it feeds. `test_cap_is_a_backstop_not_an_operating_constraint` fails any cap below `max_posts × 5`, the observed comments-per-post ceiling — which makes re-creating this failure a test failure rather than a judgement call. Both were probed by perturbation, not assumed | structural change | shipped |

The level-3 and level-5 mechanisms were verified by breaking them on purpose:
setting `LANE_REQUEST["author"]["cap"]` back to 40 fails both guards, and
restoring it returns 21 green.

**Verified live.** The re-pull with the new caps returned 246 items and **50
posts spanning 2026-10-22 to 2026-10-28** — the full week, against 6 posts and
one day under the old cap. Both lost days came back (10-24: 4 posts, 10-27: 9).
`maxPosts: 50` bound exactly, as predicted; `maxItems: 250` never bound. Cost
$0.49 against the ~$0.08 a starved pull was costing.

Verifying this fix exposed two further faults, both of the same class and
neither visible from inside this postmortem's evidence:

- `scan-triage.py --archive` wrote 60 of those 246 items and reported success,
  which briefly looked like the cap fix having failed. Separate postmortem:
  [`2026-10-28-triage-archived-a-quarter-of-the-dataset.md`](2026-10-28-triage-archived-a-quarter-of-the-dataset.md).
- The run cost $0.49205 against a **default `maxTotalChargeUsd` of $0.50 that
  nobody set**. A normal week finished $0.008 under an invisible ceiling that
  would have truncated a busier one exactly as the item cap did. Now set
  explicitly to $1.50 on both calls.

The second of those is worth stating plainly: fixing a cap I could see
immediately exposed a cap I could not, with the same failure mode. "Cap each
dimension at its own knob" is incomplete advice unless every knob is set
explicitly rather than inherited.

The corrected `maxPosts` finding was propagated to all three places the
miscount had reached — the comment-archive prompt, the weekly recall-audit
prompt (which repeated it as *"a soft target the actor does not honour"*), and
the 2026-10-14 cadence-history entry, which now points here rather than
restating the error as fact.

## Open items

Cadence was considered and **declined**: raising the comment archive to daily
would have cost real money and left the starvation in place, since a starved
pull covers one day regardless of how often it runs. Fixing the cap makes the
3x/week cadence sufficient — 50 posts reaches well past the longest gap. If
`feed_coverage` reports holes again with the cap at 250, cadence becomes the
real answer and this decision should be revisited.

Nothing else is open.
