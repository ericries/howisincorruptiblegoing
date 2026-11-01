# The sidebar remembered its own decisions in prose, so a reason that had stopped binding kept being applied

**Date:** 2026-10-31
**Found by:** me, during the sidebar job, then confirmed against git. The cron prompt had installed a tripwire — "a FOURTH pass-over must be argued on its merits" — which is what forced the re-derivation. The tripwire worked; it just fired on the fourth try rather than the first.

## What happened

The Fourth Effect summit shipped on 2026-10-24: a 200-plus invitation-only
convening of founders and investors whose programme page names *Incorruptible*
as the framing, with Eric not speaking. Institutional adoption, which
`SCAN-PROTOCOL.md` calls the strongest form of momentum evidence.

It was passed over for the What's New rail on every change after it shipped,
each time on one stated ground: **adding it would take the media column to
three, and media had twice been the column that needed cutting.** That
objection was true and it was also never the binding constraint. It assumed the
swap would be made against a non-media entry. A media-for-media swap leaves the
rail at 2/2/2/2 and the objection evaporates. Tonight it went in that way, and
nothing about the entry or the rail had changed — only the axis of comparison.

The reason it survived re-use is that it was stored as a **sentence in a cron
prompt that I rewrite by hand each night**, not as anything derivable. A
sentence can be re-read; it cannot be recomputed. Two other failures in the
same paragraph have the same cause:

- It asserted "SOSV is the last event" for days after Corporate Rebels
  announced a 19–20 November date. The prompt had to be corrected by hand, and
  carried the correction as a shouted retraction rather than simply being right.
- On 2026-10-29 the laptop was shut, the job did not fire, and the paragraph
  went stale. The 10-30 run had to note that it "re-derived the rail from the
  entries rather than from the previous paragraph" — the fallback was already
  the correct method, used only when the prose was visibly broken.

Measured: the rail's full history was recoverable from git the entire time, in
one command per commit. Nobody had ever run it. A reconstruction of the last
thirty days took under a minute and showed the invariant had held (n=8 at every
commit) and exactly which changes were made when.

The same shape produced a second, unrelated-looking bug the same evening. The
comment archive wrote its watermark `if added` — only when a cycle kept
something. 2026-10-31 judged eleven X candidates and correctly kept none, so a
completed cycle left no record it had run. The cause is identical: the thing
that mattered (**did judgment happen**) was never recorded, so the code had to
infer it from a proxy (did we keep anything), and the proxy was wrong in the
common case. The prompt compensated with prose there too — "a SKIPPED comment
is recorded nowhere, so the same rejects return to the queue every run — judge
them consistently rather than drifting", which asks my memory across nights to
do a mechanism's job.

## Five whys

**1. Why did it happen?** The objection "that takes media to three" was carried
forward verbatim from one cycle to the next instead of being re-derived against
the rail as it stood.

**2. Why was that possible?** It was prose in a prompt. Nothing recomputed it,
and nothing could: the statement had no inputs, only a reader.

**3. Why did that condition exist?** The sidebar job's entire memory — the
current eight, the queue, the stated reasons — lived in a paragraph I rewrote by
hand each night. That paragraph was the only state the job had.

**4. Why was it not already prevented?** Because the state looked free. Writing
a sentence costs nothing at the moment you write it, and the cost lands later,
on a different night, as a decision quietly made on stale grounds. The repo
already had the counter-example in `data/site-spotlight.json`, where the
spotlight job appends a record per run precisely so the next run can derive what
it needs — the pattern existed and was not applied here.

**5. Why does the system allow that class of thing?** There is no rule against
a prompt carrying derivable state, so prompts accrete it. Every job's prompt is
hand-maintained, which makes every one of them a candidate for the same decay;
the sidebar prompt had reached 10,125 characters, most of it state rather than
judgment. The general form: **when a prompt states something the repository
could compute, the prompt will eventually be wrong and nothing will notice.**

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | The Fourth Effect is on the rail, swapped media-for-media against the weaker media slot, composition unchanged at 2/2/2/2 | fix | shipped |
| 2 — the local condition | `scripts/sidebar-state.ts` derives the rail, its composition, its full change history from git, and a pass-over count per un-featured candidate. Retired entries are excluded — the first run ranked Design Observer and Stanford eCorner at the top of "passed over" when both had simply had their turn | mechanism | shipped |
| 3 — the process | the prompt no longer contains the rail, the queue or the reasons. It opens by running the script and says so explicitly: "Do not read the rail out of this prompt — it is not here any more, on purpose." CRONS.md shrank by 400 characters and lost its most decay-prone paragraph | mechanism | shipped |
| 4 — why it wasn't caught | the rail invariant is now a test over the real entries, not a grep I ran by hand at the end of the job. `index.astro` filters self-amplification and then `.slice(0, 8)`, so a ninth flag or a filtered-out flag renders a short rail in silence; `tests/sidebar-state.test.ts` fails the pre-commit hook instead. Verified to have teeth by flagging a ninth entry and watching it fail | test | shipped |
| 5 — the system | the same defect in the comment archive is fixed at the root rather than by flipping the gate: a skip is now a recorded judgment (`data/archive/linkedin-comments/.skipped.json`, with its reason), which stops rejects re-entering the queue AND gives the code the evidence it was inferring. The watermark follows judgment, not keepers; an empty verdicts file still writes nothing, which is the distinction `if added` was reaching for and could not express | structural change | shipped |

A deliberate non-change: the first attempt at level 5 was to write the watermark
unconditionally. That broke an existing test —
`test_the_watermark_is_not_written_when_nothing_was_applied` — which encoded a
real distinction I was about to flatten. The test was right. Recording skips is
what made both behaviours expressible at once.

## Open items

- Every other cron prompt is still hand-maintained and carries derivable state
  to some degree; the evening scan is 21.6k characters and is the next
  candidate. No mechanism prevents the same decay there. **This is the
  outstanding job and it is now twice-identified.**
- `2026-10-21-cranlana-defying-gravity-global-ethics-day` carries `date`
  2026-10-14 while its id says 10-21. Surfaced by the new report; not
  investigated.
- 57 entries fail the live quote gate corpus-wide, still untriaged — carried
  over from `2026-10-31-the-elision-convention-one-gate-never-learned.md`.
