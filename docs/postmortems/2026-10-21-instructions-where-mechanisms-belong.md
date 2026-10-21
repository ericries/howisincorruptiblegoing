# Instructions where mechanisms belong

**Date:** 2026-10-21
**Trigger:** `docs/CRONS.md` — the file whose own header calls it "the source of
truth" — had drifted behind all seven live cron prompts for the third time in
three days.

## What happened

The watchdog's daily roll copied each job's **live, in-memory** prompt forward and
re-created the cron from it. `docs/CRONS.md` was updated separately, afterwards,
by hand. Two copies of every prompt existed: the one that actually executed, and
the one that was committed. The executing copy won every time.

Three hand re-syncs in three days (Oct 19, 20, 21). On Oct 20 a commit message
claimed a CRONS.md edit that had **silently failed** — the anchor it matched was
in the live cron, not in the file.

The cost was not untidiness. Session crons are in-memory, so **a lesson learned
during a scan lived only in a cron and died when the session ended.** The entire
reason this schedule lives in the repository is to survive a change of machine,
and the prompts were the one part that did not.

## Five whys

**1. Why did CRONS.md drift?**
Because the roll read from memory and the file was updated by hand afterwards.
Nothing connected them except my remembering to do it.

**2. Why were there two copies?**
Because a prompt has to be a string in memory to execute (`CronCreate` takes
text) and a file in the repo to survive. Nobody built a read path from the repo
to `CronCreate`, so the link between them was discipline, not plumbing.

**3. Why wasn't that read path built, when the drift kept recurring?**
Because each time I noticed, the cheapest available fix was to re-sync the file,
and it worked. The symptom cleared every time. Each individual re-sync was a
rational local choice; the pattern across three of them was not. I was treating
"the doc is stale" as the problem rather than "nothing exists that keeps the doc
fresh."

**4. Why did "just re-sync it" keep looking like the fix?**
Because the watchdog prompt *told me to*: "If you notice CRONS.md has drifted,
re-sync it in STEP 2 and commit." I wrote that line myself on 2026-10-20, as the
fix for that day's drift. **I encoded the manual workaround into the automation**,
which made the workaround the official process and stopped anyone asking why it
was needed. A checklist item reading "notice X and manually fix it" is a bug
report that has been promoted to policy. It is also self-defeating in the
specific case: the instruction to re-sync the file was inside the prompt that was
itself drifting.

**5. Why encode a workaround instead of removing the need for one?**
Because I have been authoring these prompts as **instructions to a future me**
rather than as **a system**. An instruction says "remember to do X"; a mechanism
makes X impossible to forget. Measured today: **41 of 94 paragraphs across the
seven prompts (43%) carry a "remember to" instruction** — NEVER, do not, be sure
to, check that, before writing, verify, confirm. The week's failures were almost
all things that *were written down* and still not done: grep before writing an
entry (written down; shipped a duplicate anyway), compute the weekday (written
down after the first error; got it wrong twice more the same day), verify in the
DOM (written down; 58 headshots rendered nowhere for weeks).

Prose does not execute. Every line of it is a coin flip weighted by how tired the
reader is.

## What shipped

**The read path.** `scripts/cron-prompt.py <job>` extracts a prompt from
CRONS.md verbatim; the watchdog roll and session-start restoration both use it.
The instruction "re-sync the doc" is deleted, not improved — there is nothing to
re-sync. A lesson must now be written into CRONS.md to survive the next roll,
which puts it in version control by construction. Nine tests, including one that
asserts each prompt names its own job so a mis-pasted block fails loudly.

Syncing also exposed **two live contradictions** in the watchdog prompt: one
paragraph said "carry the live prompt forward" while another said read from the
file, and the fast-finish rule still rested on "creating a replacement after its
fire time loses the day," which the 2026-10-20 probes disproved. Contradictory
instructions four lines apart is exactly what produced the 2026-10-19 failure.

## The standing rule this leaves

**Before writing "remember to" into a prompt, ask what would make it
unforgettable instead.** A check in lint, a test, a line in a script that already
runs. Prose is the fallback for things genuinely requiring judgment — what to
ship, how to phrase a title — not for things a computer can decide.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — CRONS.md was stale | synced the twelve drifted lessons into all seven sections | fix | shipped |
| 2 — two copies with no link | `scripts/cron-prompt.py` extracts a prompt from the file; the roll reads it | mechanism | shipped |
| 3 — the read path was never built | session-start restoration reads the same path, so there is one way in | structural change | shipped |
| 4 — the prompt told me to re-sync by hand | that instruction is deleted, not improved — there is nothing left to re-sync | structural change | shipped |
| 5 — instructions written where mechanisms belong | three instructions became mechanisms; `postmortem-lint.py` now rejects a prevention that reads "remember to" | structural change | shipped |

The level-five row is the one that generalises, so it got the most work. Audited
every "remember to" across the seven prompts and mechanised what could be:

| prompt instruction | mechanism | status |
|---|---|---|
| "re-sync CRONS.md when it drifts" | deleted — `cron-prompt.py` read path | shipped |
| "grep for the source_url before writing" | lint fails on same-type duplicate `source_url`s | shipped |
| "write the watermark when the job finishes" | automatic in `archive-social-comments.py` | shipped |
| "compute the weekday, never eyeball it" | lint fails when `title`/`attribution_title` names a weekday the date contradicts | shipped |
| "grep dist/ after attaching an image" | `check-images-render.py` reads the build and reports orphaned image paths | shipped |
| "be fast; don't run past 9:00" | stays prose — a genuine judgment call | declined |

The weekday check found two more shipped errors of the Berkeley class: Rotman
said "Monday August 18" (a Tuesday) and Quebec House said "Sunday September 7" (a
Monday). Both corrected. The image check found one orphan after the reaction fix
— Dott Chen's headshot, because the social byline was gated on LinkedIn in two
places and his post is on X. Generalised to any social platform, with the
matching mark; the comment archive had started feeding X the day before, so it
would have recurred.


## What the new check found immediately

Turning same-type duplicates into a failure surfaced two pairs on the first run,
and neither was a false positive:

**LIFT Economy** — `2026-05-05-lift-economy-next-economy-now` was sourced to Ryan
Honeyman's LinkedIn announcement rather than to the episode. Repointed at
`lifteconomy.com/blog/eric-ries` with the announcement kept in `source_urls`,
which also satisfies "judge reach at the destination."

**Thought Economics** — two `media` entries on one interview. The `created_at`
fields settle which is which: the 05-29 entry was written the day it shipped; the
05-21 entry was added **2026-07-15**, two months later. Checking the interview to
decide which date was right turned up something worse than a duplicate.

The 05-21 entry's blockquote read *"Governance is not bureaucracy — it is the
most important product a founder will ever design,"* attributed to Eric in the
title. The interview contains neither half as written. Eric says governance "has
become very convenient for a lot of people to hide behind by making it sound
boring"; the phrase "the most important product you'll ever design" is **Brian
Chesky's**, quoted by Eric about companies, not governance. The blockquote is a
composite of two speakers, and it had been live since 2026-07-15.

That is the exact failure `CLAUDE.md` names first — "Never paraphrase,
composite, or summarize" — and it survived three months of scans, a quote
verifier that skips unreachable pages, and a duplicate warning nobody was
required to act on. The entry is removed; the correctly-sourced 05-29 entry,
whose quote verifies verbatim, stands.

**This is the argument of the postmortem in miniature.** The rule against
composited quotes was written down, prominently, in the first file every session
reads. What caught the violation was not the rule but a check that could fail a
commit — and only once the check was made capable of failing one.

## A note on the 43% metric

The "remember to" count across the seven prompts was 41/94 before this work and
41/94 after, because deleting two instructions and adding two explanations is a
wash. The number is a diagnostic for noticing a pattern, not a target to drive
down — optimising it directly would just mean writing the same instructions in
words that dodge the regex. What matters is the count of instructions that have
been made unnecessary, which is three.
