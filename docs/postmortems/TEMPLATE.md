# <what broke, in one line>

**Date:** YYYY-MM-DD
**Found by:** <who or what — and if a human asked, say so; that is the finding>

## What happened

<The facts, with evidence. Timestamps, counts, file paths, command output. No
interpretation yet.>

## Five whys

**1. Why did it happen?**
**2. Why was that possible?**
**3. Why did that condition exist?**
**4. Why was it not already prevented?**
**5. Why does the system allow that class of thing?**

Stop early only when a why genuinely bottoms out, and say that it did. Carrying a
why past its evidence invents a cause; two of the three wrong diagnoses on
2026-10-20 came from reasoning one level beyond what had been measured.

If an explanation rests on how the runtime behaves, **probe it** rather than
inferring it — see the top of `SCAN-PROTOCOL.md`. "It has not happened yet" is not
"it does not happen."

## Prevention, proportional at each level

**One row per why reached. A postmortem that only fixes level 1 is the failure
mode.** The investment should scale with depth: the immediate instance is cheap
to fix and prevents nothing; the systemic cause is expensive and prevents the
class.

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | | fix | shipped / open / declined |
| 2 — the local condition | | check or test | |
| 3 — the process | | mechanism | |
| 4 — why it wasn't caught | | mechanism | |
| 5 — the system | | structural change | |

`kind` matters more than it looks. **A prevention that reads "remember to X" is
not a prevention** — it is the instance fix wearing a hat. Prefer, in order:

1. make the failure impossible (remove the path)
2. make it fail loudly (lint failure, failing test)
3. make it visible (a check something already runs)
4. only then, prose in a prompt — and only for genuine judgment calls

`declined` is a legitimate status with a stated reason. "Not worth the
complexity" is an answer; silence is not.

## Open items

<Anything above with status `open`, restated so it can be found. If nothing is
open, say so explicitly — an empty section reads as an oversight.>
