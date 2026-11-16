# The book-tour strip stopped showing new events, and only a human noticed

**Date:** 2026-11-16
**Found by:** Eric, by looking at the site — "the 'book tour' event strip at the top seems to have stopped updating". No check, no test and no scan report had anything to say about it.

## What happened

`src/components/UpcomingStrip.astro` renders an event card only when the entry
carries `type_metadata.city`:

```js
const hasCity = typeof meta.city === 'string' && meta.city.length > 0;
if (!hasCity) return false; // in-person only (must have a city)
```

Two events shipped on 2026-11-16 without it — ZEBRAHOOD 2026 (Tokyo, 27 Nov)
and Yale SOM 50 (New Haven, 2 Dec) — so the strip's forward edge was a single
card, Corporate Rebels on the 19th, and looked frozen.

Measured across the corpus that day: **15 of 21 event/podcast entries since
2026-10-01 had no `city`**. Six were genuinely virtual and correctly excluded
(SOSV "free and virtual", B Academics "Virtual", the HBS guest slot by Zoom).
The two above were the live defects.

Every other surface was correct throughout. The entries' own pages, the What's
New rail, the timeline and RSS all rendered them. The strip was the only
consumer of `city`, and nothing watched it.

Two further defects surfaced while fixing it, both from the same root:

- `findReshareDuplicates` had **never run**. It needs `source_urls`, which was
  absent from the entry projection lint builds, so it had no second id to match
  on and reported nothing for its whole life.
- `type_metadata` holds **42 distinct keys, 20 of which no component reads** —
  including `audience`, set on 79 entries and rendered nowhere, and `venue`, a
  three-use near-duplicate of `city` (50 uses).

## Five whys

**1. Why did it happen?** ZEBRAHOOD and Yale SOM shipped without
`type_metadata.city`, which is the field the strip filters on.

**2. Why was that possible?** Nothing required it. `city` is load-bearing for
one component and optional in the schema, and no part of the writing path — the
scan prompts, the entry template, lint — mentions it. An entry without it looks
complete, because on its own page it is.

**3. Why did nobody notice for weeks?** Because the failure is invisible from
every surface except the one that broke. There was no view answering "what does
the strip contain?", and no check comparing a component's input requirements
against the corpus. The only available observer was someone looking at the page.

**4. Why was it not caught when a check for exactly this was added?** Because
`lint-entries.ts` passed a hand-listed **projection** of each entry — `file,
type, date, id, parent_id, source_url` — to every check. A check needing
anything else received `undefined` and reported "no findings", silently,
because absent and empty look identical. The new strip check read
`type_metadata`, which was not in the list, so it flagged all three future
events including the two just given a city. Six unit tests passed throughout:
they fed synthetic objects with the right shape, so they tested the function
and not the seam. The only tell was blank titles in the warning's own output.

**5. Why does the system allow this class of thing?** Because `type_metadata`
is an untyped `Record<string, unknown>` shared by every entry type, and nothing
enumerated it. A key can be forgotten, misspelt, or invented, and all three
produce the same result: silence. 42 keys are in use and 20 have no reader, so
the bag had already drifted into a mix of live fields, dead fields and
near-duplicates with no way to tell them apart.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | `city` and `signup_url` added to both entries, from the public pages they already cite; strip back to 42 cards with 3 ahead | fix | shipped |
| 2 — the local condition | `findEventsMissingFromStrip` + a lint warning naming any FUTURE event with no city and no virtual marker; scoped to future because 19 past events legitimately lack one and a rule firing 19 times a commit is noise | check | shipped |
| 3 — the process | two tests read the **real corpus** the way the site reads it: no future event missing from the strip, and every future event either placed or declared virtual. The automated observer that did not exist | test | shipped |
| 4 — why it wasn't caught | lint now spreads the **whole entry** instead of a hand-listed projection, so the next check cannot silently receive `undefined`. Removing the path, not patching this one check | mechanism | shipped |
| 4b — the check it had disabled | `findReshareDuplicates` ran for the first time and fired. Its severity now follows the documented mixed-type policy: same-type fails, mixed-type warns, because a podcast and a reaction to it are two entries by design | mechanism | shipped |
| 5 — the system | `src/lib/type-metadata-keys.ts` closes the set: every key listed with its consumer, or with `unread` and a reason. A key outside the registry fails a test, so a typo or an invention stops at the commit instead of being ignored for months | structural change | shipped |
| 5b — the dead keys | 20 keys no component reads, kept rather than deleted and now documented as unread. Deleting a field across hundreds of entries to tidy a list is the worse trade; knowing that writing one does not publish it is the point | documentation | shipped |

`title` and `attribution_title` drifting unchecked is a related finding from the
same day, fixed separately in `docs/DRAFTING.md` and `summary_tics.py` — the
median title ran 32–42 characters in December and 141 in September, with the em
dash going from 0% of titles to 87%. It is recorded there rather than here
because its cause is the one the summary drift already documented: a field with
no number attached has nothing to drift from.

## Open items

None of the rows above are open.

Two things are deliberately **declined** rather than fixed:

- **The 19 past events with no city.** Mostly LinkedIn Lives and livestreams
  that never needed one. The handful with real venues — Torino, Oakland,
  Durango, Aspen — need their sources re-read before a city is asserted, and a
  wrong city on a live page is worse than a missing one. Left for a pass where
  each can be verified rather than guessed.
- **Deleting the 20 unread keys.** Some are real data a future surface or the
  social agent may want. Listed as unread instead, which is the information
  that was actually missing.
