# Three crons missed, and two wrong diagnoses in two days

**Date:** 2026-10-20
**Found by:** Eric, asking "did the cron fire this morning?" at 11:38 — the second
consecutive day a missed scan was surfaced by a human rather than by the system.

## What happened

Three scheduled jobs did not run on 2026-10-20:

| job | due | ran |
|---|---|---|
| morning content scan | 9:07 | no |
| Goodreads review scan (Mondays) | 10:33 | no |
| LinkedIn comment archive (Mon/Wed/Fri) | 10:47 | no |

Evidence: the newest file in `data/archive/linkedin-raw/` and `twitter-raw/` was
from 2026-10-19 18:34 (the evening scan); `.scan-state.json` carried no Oct 20
watermark past that run; the only commits on Oct 20 were the two from the
watchdog turn itself.

Two explanations were ruled out. The machine was awake throughout — `pmset -g log`
shows `powerd` holding `PreventUserIdleSystemSleep` for the hour before 11:38 and
an active Zoom session. And the REPL was idle from 9:19 onward, which covers both
the 10:33 and 10:47 slots with their full 15-minute jitter windows.

The one property all three share: each was **recreated during the 8:37–9:19
watchdog turn**, and each then failed at a match later the same day. The working
hypothesis is that recreating a recurring cron advances its schedule past the next
match. As of this writing that is **unverified** — a probe job created at 11:38
with an 11:43 match is pending.

## Five whys

**1. Why did the three jobs not run?**
Unknown mechanism. All three were rolled earlier the same day and then missed a
same-day match. The evening jobs (18:03, 19:27) were not yet due, so they offer
no counter-evidence either way.

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
