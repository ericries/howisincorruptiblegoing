# The morning scan missed, and three wrong diagnoses in two days

**Date:** 2026-10-20
**Found by:** Eric, asking "did the cron fire this morning?" at 11:38 — the second
consecutive day a missed scan was surfaced by a human rather than by the system.

## What happened

The **morning content scan (9:07 daily) did not run** on 2026-10-20. Evidence: the
newest file in `data/archive/linkedin-raw/` and `twitter-raw/` was from 2026-10-19
18:34 (the evening scan); `.scan-state.json` carried no Oct 20 watermark past that
run; the only commits on Oct 20 were the two from the watchdog turn itself.

Two explanations are ruled out. The machine was awake throughout — `pmset -g log`
shows `powerd` holding `PreventUserIdleSystemSleep` for the hour before 11:38 and
an active Zoom session. And the REPL was idle from 9:19 onward.

**Correction, written an hour after the first draft of this file.** I originally
reported *three* missed jobs, adding the Goodreads scan (10:33) and the LinkedIn
comment archive (10:47). Both were fine. **2026-10-20 was a Tuesday**; Goodreads
runs Mondays and the comment archive Mon/Wed/Fri, so neither was due. Both had run
correctly the previous day — `data/archive/goodreads/2026-10-19.json` at 11:03 and
the two Oct 19 comment files at 11:18. I inferred "did not run" from the absence of
a today-dated archive file without checking whether the job was due today, and
`CronList` had printed "Every Monday at 10:33 AM" right in front of me. I had also,
thirty minutes earlier, computed that Oct 27 is a Tuesday while fixing an event
entry that said "Monday October 27" — which makes Oct 20 a Tuesday too. Same error
class twice in one session: a weekday assumed instead of computed. The cost was not
only a wrong report — it was ~$0.30 of Apify budget re-pulling two cycles that did
not need pulling, on a capped account.

What survives the correction: one daily job missed its slot, and a **probe job
created at 11:38 with an 11:43 match also did not fire** (jitter window closed at
~11:58, REPL idle from 11:48). The probe is now the primary evidence, where before
it was corroboration for a trio that turned out to be a single.

## Five whys

**1. Why did the morning scan not run?**
Unverified, but the probe is a clean direct test: a recurring job created at 11:38
did not fire at its 11:43 match the same day. Both the morning scan and the probe
were created minutes before a same-day match and neither fired, which points at
recreation advancing the schedule past the next match. A second probe with an
89-minute lead is pending to test whether lead time is the variable.

**1b. Why was the failure reported as three jobs when it was one?**
Because "no archive file dated today" was treated as "the job did not run,"
skipping the question of whether the job was due today. Two of the seven crons are
not daily. The check is one line of Python against the cron expression and the
weekday; I ran neither.

**2. Why is the mechanism still unknown, two days into this failure?**
Because on 2026-10-19 I explained the same symptom with the first plausible story
— the rolls had run after 9:07, so the replacement was created past its fire time
— and shipped a fix based on it instead of testing it. The story fit that day's
facts exactly: a YouTube backfill really had pushed the rolls to ~9:08. A single
consistent case felt like a confirmed mechanism. It isn't one.

**3. Why was an untested explanation good enough to ship a fix on?**
Because the fix looked free. Reordering the watchdog to do rolls first cost
nothing if the diagnosis was wrong — or so it seemed. The hidden cost is that a
fix consumes the evidence: had today's scan fired, I would have credited the
reordering and closed the case. It didn't fire, so I produced a *second* story
(the turn ran long, 8:37–9:19, and a cron cannot fire mid-turn), moved the
watchdog to 8:17, and shipped that too. Two speculative fixes, one unmeasured
mechanism, zero experiments.

**4. Why did no automated check catch a missed morning cycle before Eric asked?**
`scripts/scan-coverage.py` exists precisely for this and would have reported it
immediately. But it only runs in two places: the watchdog at 8:17 — *before* the
failures — and the Sunday recall audit. Nothing runs after the morning window. The
detector is sound; its scheduling makes it structurally blind to a same-day miss.

**5. Why is the only check scheduled inside the window it cannot observe?**
Because the entire pipeline is hosted inside the thing being monitored. Crons
restore crons, a cron checks coverage, the watchdog renews itself. Eric's
constraint is right and not in question — repo-only, no launchd, no machine-local
state, so the system survives a change of platform. But I translated "nothing
outside the repo" into "nothing outside the cron cohort," and **a monitor that
shares a failure domain with its subject cannot report that domain failing.**
That is why the detector of record, two days running, has been Eric reading the
site.

## What I am NOT doing

Shipping a third restructure of the roll mechanism. The lesson of whys 2 and 3 is
that I have been fixing a mechanism I never measured; doing it again today would
repeat the error with more confidence. The probe settles the question first.

If the probe confirms that recreation skips the next match, the fix is structural
and clear: **each job rolls itself at the end of its own run**, so a roll always
happens immediately *after* a fire and can never skip an occurrence. The watchdog
then reverts to recreate-if-missing plus coverage, and the two weekly jobs
(Goodreads, recall audit) need the watchdog to roll them on a day they are not
due. If the probe fires normally, the hypothesis is dead and the real cause is
still open.

## Preventive measures

1. **Measure before fixing.** A behavioural claim about the runtime gets a probe
   job, not an inference from one case. Added to `docs/SCAN-PROTOCOL.md`.
1b. **Compute the weekday; never assume it.** Before calling a job missed, check
   it was due: `python3 -c "import datetime; print(datetime.date.today().weekday())"`
   against the cron expression. `scan-coverage.py` should learn the cadence of each
   source so it cannot report a Monday-only job missing on a Tuesday either.
2. **A check that runs after the morning window**, not only before it. Cheap:
   `scan-coverage.py --days 1` costs nothing and takes seconds.
3. **An out-of-band heartbeat.** Each scan writes a committed heartbeat
   (timestamp + source) and a tiny scheduled GitHub Action — in the repo, so it
   survives a platform change, and ~1 min/month against the 100-minute budget —
   flags a stale heartbeat. This is the only measure that breaks the shared
   failure domain in why 5. It needs Eric's call because it notifies him.
4. **Note the observability gap:** `CronList` does not expose a job's next-fire
   time, so the watchdog cannot verify its own rolls took effect. Any fix has to
   be robust without that signal.

## Corrections to the record

- The 2026-10-19 postmortem's root cause ("slow work before the rolls") is at best
  incomplete. Ordering was a real bug and worth fixing, but it was not what
  stopped the morning scan on either day.
- `docs/CRONS.md` and the watchdog prompt now carry two narratives — rolls-first,
  and finish-by-9:00 — both written from unverified diagnoses. Both stay until the
  probe resolves, then get rewritten from what is actually true.
