# The catch-up tool reported two false misses the morning the clocks changed

**Date:** 2026-11-01
**Found by:** the start-of-cycle `scan_catchup.py` run, by noticing that both reported fire times were exactly one hour later than the cron expressions that produce them. Nothing was re-run: the discrepancy was checked before it was acted on.

## What happened

DST ended in America/Los_Angeles at 02:00 on 2026-11-01. The first
`scan_catchup.py` run afterwards said:

```
Catch-up: 2 job(s) owe work.
  evening-scan     last ran 2026-11-01T01:55:00Z
                   missed: Sat 31 19:03
  goodreads        last ran 2026-10-26T18:03:29Z
                   missed: Mon 26 11:33
```

Both were false. The evening scan's cron is `3 18 * * *` and it was reported
missing a **19:03** slot; Goodreads is `33 10 * * 1` and was reported missing
**11:33**. Each stated time is its own expression plus one hour.

The evening scan had in fact run on 2026-10-31 at 18:55 PDT — the watermark
`2026-11-01T01:55:00Z` — comfortably after that day's real 18:03 PDT slot.
Goodreads ran 2026-10-26 at 11:03 PDT, after its real 10:33 slot.

The cause is in `_slots`, which builds each fire time as

```python
_dt.datetime.combine(day, _dt.time(hour, minute), tzinfo=start.tzinfo)
```

and took `start.tzinfo` from `overdue`'s default,
`_dt.datetime.now().astimezone().tzinfo`. **That expression returns a fixed
offset — whatever the offset is at the moment it is called — not a zone.** On
1 November it is UTC−08:00. Building 31 October 18:03 with a −08:00 offset
yields 02:03Z, where the real 18:03 PDT was 01:03Z. The watermark at 01:55Z
falls between the two, so a completed run looked like a miss. The report then
rendered the slot with `.astimezone()`, which *does* use the real DST-aware
zone, turning 02:03Z back into 19:03 PDT — which is why the wrong hour was
visible in the output at all.

What this would have cost: two scans re-run for nothing, against a metered
Apify account. CLAUDE.md already records the precedent — "On 2026-10-20 a
Monday-only scan was reported missed on a Tuesday and re-run at real cost" —
and that note is why the times were checked against the expressions first.

`choose_posted_limit` was checked and is unaffected: it works on UTC deltas via
`total_seconds()`, which no transition disturbs.

## Five whys

**1. Why did it happen?** Fire times for past dates were constructed with
today's UTC offset, so every slot on the other side of the transition moved an
hour.

**2. Why was that possible?** The default timezone was
`datetime.now().astimezone().tzinfo`. It reads as "the local timezone" and is
actually "the local offset, now" — a `datetime.timezone`, which has no concept
of a transition.

**3. Why did that condition exist?** The function was written to fix an earlier
timezone bug, recorded in its own docstring: cron times are local, watermarks
are UTC, and comparing them directly turned the 18:03 scan into an 11:03 slot.
The fix converted both sides to "local" using the handiest expression for it.
That expression is correct 363 days a year.

**4. Why was it not caught?** Every existing test either passed an explicit
fixed-offset tz or used dates inside a single offset regime. None crossed a
transition — the one condition under which "local offset" and "local zone"
differ. The suite was built from the bugs already seen, which is exactly the
set of bugs it cannot find.

**5. Why does the system allow that class of thing?** The tool that reports
whether scheduled work happened is itself time-dependent, and nothing compared
its output to the schedule it was reporting on. The wrong hour was printed next
to a job whose cron expression states the right hour, and the two were never
checked against each other. A false *missed* costs a re-run; a false *nothing
overdue* hides a real gap. It became wrong silently, at 02:00 on a Sunday.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | `_local_zone()` resolves the machine's real zone (`TZ`, then `/etc/localtime`), falling back to a fixed offset only when no zone database is reachable | fix | shipped |
| 2 — the local condition | `test_a_slot_before_a_dst_change_is_not_shifted_by_an_hour` reproduces 2026-11-01 exactly: a run at 18:55 PDT on 31 Oct, evaluated at 08:11 PST on 1 Nov, must not be overdue | test | shipped |
| 3 — the process | `test_every_job_fires_at_the_local_hour_its_cron_states_year_round` asserts, for **every** job in `JOBS`, that the next fire time rendered in real local time lands on the hour and minute its expression names — probed either side of both the autumn and spring transitions. A job added later is covered without anyone remembering to | test | shipped |
| 4 — why it wasn't caught | the production default is now itself under test, not just injected doubles: `test_the_default_zone_is_dst_aware_not_a_fixed_offset` asserts `_local_zone()` is not a `datetime.timezone` — the fixed-offset class that was precisely the defect. Verified to have teeth by restoring the old default and watching it fail | test | shipped |
| 5 — the system | the invariant at level 3 is the cross-check that was missing: the schedule and the report of the schedule are now compared to each other by machine rather than by a reader who happens to look. Making the report self-checking at runtime as well was considered and **declined** — the test covers the same invariant, runs in the pre-commit hook, and a runtime assertion in a monitoring tool that fails closed would suppress the report it exists to produce | structural change | declined |

## Open items

None from this. Items carried from earlier postmortems — the 57 untriaged live
quote-gate failures, and the evening-scan prompt's derivable state — remain
open and are tracked there.
