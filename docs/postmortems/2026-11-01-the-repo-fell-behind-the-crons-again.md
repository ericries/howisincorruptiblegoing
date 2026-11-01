# The repo fell behind the live crons for the third time, and the fix each time was to do it by hand again

**Date:** 2026-11-01
**Found by:** the watchdog roll, comparing the live evening-scan prompt against what `cron-prompt.py` produced. Not by a check — by noticing that seven things I expected to see in the file were not there.

## What happened

`docs/CRONS.md` was **seven passages behind** the live evening-scan cron. The
missing text was lessons from 2026-10-29 and 10-30: the METR clip as the
negative case for the argument-not-plays test, Camilo Barros as attendee notes
in a new register, Dougal Shaw on mining a name-list recap, David Banks and
Michael Paradise as in-house institutional adoption, two grep-before-you-skip
cases, and the `git status` check for untracked entries.

The watchdog instructs the roll to read from the file. **Had I done exactly
that, all seven would have been deleted** — the live cron is the only other
copy, and it is replaced on every roll.

This is not the first time. `git log` shows the repair performed under its own
recurring commit title:

```
6954823 docs: write back the lessons the 10-26 roll carried forward
0c68baa docs: write back the lessons the 10-25 roll carried forward
8251814 docs: CRONS.md was seven passages behind the live evening-scan prompt
```

Three occurrences, three hand repairs, no mechanism. The 2026-10-21 fix that
introduced `cron-prompt.py` made it *possible* to roll from the file; it never
made it *checkable* that the file was current.

## Five whys

**1. Why was the file missing seven lessons?** A previous roll improved the
evening-scan prompt while composing the `CronCreate` call and did not write the
improvement back to `docs/CRONS.md`.

**2. Why was that possible?** Rolling is "read the file, pass the text to
CronCreate", and the text passes through the agent on the way. Editing it in
flight is one keystroke and leaves no trace — the same keystroke that writes a
genuinely new lesson.

**3. Why did nothing detect the divergence?** Nothing can. `CronList` returns an
~80 character preview, so the text inside a running cron cannot be read back and
compared. The divergence is undetectable by construction, which is why it had to
be *noticed* rather than *reported*, and why it was noticed only on the third
occurrence.

**4. Why did the existing size-diff shortcut not catch it?** Because it compares
the file today against the file yesterday. It is blind to file-versus-live by
design — it answers "did the repo change", never "does the repo match what is
running". It has been reported in every watchdog report for two weeks and would
never have found this.

**5. Why does the system allow that class of thing?** Because the invariant that
the whole design rests on — *the repo is the source of truth* — is stated in
prose and enforced by nobody. The repair being easy and quick is what kept it a
repair: writing back seven passages takes two minutes, so three times running it
was cheaper to fix the instance than to build the mechanism. An instance fix that
is cheap enough never graduates on its own.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | the seven passages restored to `docs/CRONS.md` and committed (8251814) | fix | shipped |
| 2 — the local condition | `scripts/cron_roll.py <job>` is now the sanctioned way to obtain a prompt, and it prints a **ROLL TOKEN** — sha and byte count of exactly the text it handed over — while recording it to `data/cron-roll-log.json`. Enriching in flight is still possible, but it now visibly diverges from a number printed beside the text | mechanism | shipped |
| 3 — the undetectable divergence | since live-versus-file cannot be read, the agent reports what it rolled: `cron_roll.py --rolled <job> <bytes>` compares it against the token and, on a mismatch, names it an unwritten enrichment and says to patch the file first. The check happens in the turn that causes it, not a week later | mechanism | shipped |
| 4 — the blind shortcut | `cron_roll.py --check` answers the question the size-diff could not: for each job, does the file still match what was last rolled? `file-ahead` means a section was edited and the live cron is now behind the repo — the opposite drift, which was equally invisible and is now a non-zero exit | mechanism | shipped |
| 5 — the system | the roll log makes the invariant auditable rather than aspirational: every handover is dated, hashed and sized, so "when did this section last reach a cron, and as what" is answerable from the repo. Bounded to the last ten rolls per job so it stays readable. **Declined**: making the watchdog refuse to roll an unverified job. The watchdog is the thing that restores everything else, and a gate that can block it trades a silent drift for a silent stoppage — the worse failure, by the same reasoning that keeps the quote gate from failing closed | structural change | declined |

Ten tests in `scripts/test_cron_roll.py`, including the byte-versus-character
trap that made the size diff lie earlier the same day.

## Open items

- The log is seeded with only the four jobs rolled byte-for-byte from the file
  today. **watchdog and evening-scan were enriched in flight and then written
  back**, so what their live crons hold cannot be attested and both report
  `never-rolled` — which is the honest answer. They also carry a known one-line
  divergence: the baseline size line was re-converged after they were rolled, so
  the live watchdog quotes a total of 89379 where the file now says 93679.
  Tomorrow's roll resolves both.
- `cron_roll.py` is not yet wired into the watchdog prompt as the required
  command; that edit lands with this commit, so it takes effect on the next roll.
