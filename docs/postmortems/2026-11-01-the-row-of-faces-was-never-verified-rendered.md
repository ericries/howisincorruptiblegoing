# Four of the nine pinned cards in the row of faces have never rendered, and they are exactly the four women

**Date:** 2026-11-01
**Found by:** Eric — *"that sisodia endorsement is really strong, let's make sure
it's sufficiently prominent."* The dead pins were found by the test written to
make that change self-verifying, within a minute of its first run. Nobody was
looking for them.

## What happened

Two findings, one cause.

**The small one.** I shipped `2026-10-29-raj-sisodia-bookshelf-of-every-leader`
with no prominence flags, and said why in the audit report: *"unflagged — his
October entry already carries a highlight and his face, and a second identical
face makes the row repetitive rather than stronger."* Sisodia co-founded
Conscious Capitalism, is on `HIGHLIGHT_ELIGIBLE_ENDORSERS` by Eric's own
direction, and said the book *belongs on the bookshelf of every leader in the
world* — the strongest form of a blurb there is. I weighed row aesthetics
against signal strength and picked aesthetics, unasked.

**The large one.** `UpcomingStrip.astro` holds `QUOTE_TAIL_ORDER`, nine ids that
fix the order of the back half of the row of faces. Four of them have never
rendered a card:

```
DEAD — no highlight  2026-03-16-endorsement-leah-solivan   Founder of TaskRabbit
DEAD — no highlight  2026-03-13-endorsement-kieran-snyder  Founder, Textio
DEAD — no highlight  2026-03-05-reader-denise-hearn        The Long Now Foundation
DEAD — no highlight  2026-01-20-endorsement-vlada-bortnik  Founder and CEO, Marco Polo
```

A pin only *reorders* a card; a card exists because its entry carries
`type_metadata.highlight`. No flag, no card, and the pin places nothing.

The four dead pins are the four women. The commit that wrote the list is
`f4be76c hero: alternate F/M in the back half of the quote row`. The alternation
it was written to produce has never existed on the page — the back half has
always rendered M, M, M, M, M. Solivan's entry also carries
`face_position: 'center top'`, a field **only the quote card reads**, so her
entry was tuned for a card that has never been built.

All four have a headshot on disk. None is on `HIGHLIGHT_ELIGIBLE_ENDORSERS`, and
none carries a `sidebar_quote` either, so none of the four appears on any
prominence surface at all.

## Five whys

**1. Why was Sisodia unflagged, and why do four pins render nothing?** Both
decisions were made against the *configuration* and never checked against the
*page*. I judged the row too repetitive without looking at it; the alternation
commit set an order without looking at it.

**2. Why was that possible?** The row of faces is assembled from two halves that
nothing joins up: the flag on an entry (which creates a card) and the pin in a
list (which orders it). Each half is individually valid — a flag with no pin
sorts into the middle, a pin with no flag is simply skipped by
`.filter(q => q !== null)`. There is no state in which either half alone is
detectably wrong.

**3. Why did that condition exist?** Because the filter was written to be
forgiving. `parseHighlight` returning `null` and a missing flag take the same
path, which is correct for the middle bucket — most highlighted entries are
never pinned — and silently wrong for a pin, which only exists *because*
somebody wanted that specific card placed.

**4. Why was it not already prevented?** It was supposed to be.
`memory/feedback_verify_in_dom.md` was written about this exact component:
*"Twice I edited Highlights.astro (dead code) when the real row was
UpcomingStrip's quoteCards. Always grep dist/index.html to confirm."* The memory
named the file, named the trap, and the pins stayed dead for seven months — the
tail pins date to March. The memory says *always verify*, which is an
instruction. `memory/feedback_mechanisms_not_instructions.md` already says what
that is worth: *"'remember to' in a prompt is a bug report promoted to policy."*
Two memories were in place, pointing at this component, and neither could fire.

**5. Why does the system allow that class of thing?** Because
`tests/ui-invariants.test.ts` tests the row's **shape** and not its **contents**.
It asserts card geometry, the first three ids of the front block, that Eyal is
in the tail, that O'Reilly is last — nine tests, all of which pass over a list
where four of nine entries are dead, because every assertion is about the
*strings in the array*. The file reads the `.astro` source and never once opens
an entry. A test suite that reads only one side of a two-sided seam will pass
forever while the seam is broken.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | Sisodia carries `highlight`, `sidebar_quote` and `featured`, and is pinned 8th in `QUOTE_FRONT_ORDER`. All three verified in `dist/index.html`: card 8 of 34 in the row, first of the three sidebar pull quotes, third of eight in What's New. Croll rotated out of the rail explicitly rather than being dropped by the `slice(0, 8)` | fix | shipped |
| 2 — the local condition | `UpcomingStrip pins point at live cards` crosses the seam: every id in `QUOTE_FRONT_ORDER`, `QUOTE_TAIL_ORDER` and `POSTER_PINS` must resolve to an entry file, and every quote pin must carry `type_metadata.highlight`. It found the four dead pins on its first run | test | shipped |
| 3 — the process | The four dead pins are carried in `PINNED_WITHOUT_A_FLAG` with their names and titles written out, because allowlisting is Eric's call and not the scanner's. A second assertion checks each name is **still absent** from `HIGHLIGHT_ELIGIBLE_ENDORSERS`, so the exception is self-retiring: the moment a name is allowlisted the test fails, and the only way to pass is to set the flag and delete the name. An exception that cannot outlive its reason is not an escape hatch | mechanism | shipped |
| 4 — why it wasn't caught | The two memories that should have caught it are being rewritten as what they actually were — `feedback_verify_in_dom` becomes a pointer to the test rather than a reminder to grep, since a memory that asks for diligence at every edit buys nothing a test does not buy once | mechanism | shipped |
| 5 — the system | The general form: **a test that reads one side of a seam is not testing the seam.** `ui-invariants.test.ts` now opens entry files, which is the first time it has read anything but the `.astro` source. **Declined**: a general "every cross-file reference in `src/` resolves" linter. The references are heterogeneous (ids, image paths, allowlist names, pin arrays) and a generic walker would need a schema per kind, which is the same work spread thinner — the seams are better named one at a time, as this one now is | structural change | shipped |

## Open items

- **Four endorsers are invisible on every prominence surface, pending one
  editorial decision.** Leah Solivan (TaskRabbit), Kieran Snyder (Textio;
  Microsoft), Denise Hearn (Long Now), Vlada Bortnik (Marco Polo) each have a
  real blurb, a headshot on disk, and a pin someone placed deliberately. Adding
  them to `HIGHLIGHT_ELIGIBLE_ENDORSERS` is Eric's call — surfaced to him
  2026-11-01. Until then the F/M alternation in the back half of the row cannot
  work, because half its cards do not exist.
- **The row now shows Sisodia at positions 8 and 10**, two cards apart, same
  face. His stronger line leads, which is right, but the repetition I originally
  flagged is real and now visible. The fixes available are to pin the October
  card into the tail (which breaks the F/M alternation the tail list exists to
  hold) or to drop its row card (which `feedback_highlights_row_grows` forbids:
  *only ADD, never trim*). Both trade against a rule Eric set, so this is his
  call too, and the page is the right place to judge it from.
