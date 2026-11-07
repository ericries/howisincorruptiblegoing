# A publisher's reshare became a second entry for a review already on the timeline

**Date:** 2026-11-06
**Found by:** me, during the evening scan — but only because Eric had sent the
article URL (`hardproblems.com/articles/incorruptible-eric-ries`) earlier in the
session and I went to fetch it for an image. Reading the article is what revealed
the byline. Nothing in the pipeline was looking.

## What happened

`content/entries/2026-11-03-hard-problems-excellent-book-every-leader.json` was
written with `created_at: 2026-11-06T17:45:00Z`, sourced to

    https://www.linkedin.com/posts/hardproblems_incorruptible-by-eric-ries-activity-7523410060706725888-lrPq

whose entire body is two sentences: *"We just published a new book review:
'Incorruptible' by Eric Ries. We think it's an excellent book that every
entrepreneur or leader should read."*

The review it announces is Daniel Burka's, and Burka was already on the timeline
as `2026-11-03-daniel-burka-rare-to-recommend-a-business-book`, sourced to the
article itself. Two entries, same date, same type (`review`), one piece of
writing.

The raw archive had recorded the relationship three days earlier. In
`data/archive/linkedin-raw/2026-11-03-keyword-bare.json` the Hard Problems record
carries:

    "repost": {"id": "7523409771211780096",
               "linkedinUrl": ".../posts/dburka_incorruptible-by-eric-ries-activity-7523409771211780096-h0kb",
               "content": "I doubt he remembers it, but Eric Ries and I ate breakfast together..."}

— the full text of Burka's post. The field was there in five archive files and no
check read it. Measured after the fix: 94 reshare pairs across 180 raw files.

The entry was never committed; it was untracked in the working tree at session
start and removed before this scan's commit. The card
`public/images/cards/2026-11-03-hard-problems-excellent-book-every-leader.png`
went with it, and the Hard Problems post is now the first `source_urls` item on
Burka's entry.

## Five whys

**1. Why did it happen?** An entry was written from a LinkedIn post without
establishing what that post was. It was a reshare with a two-sentence comment
attached; the review it pointed at was already published here.

**2. Why was that possible?** The standing guard against this
(`memory/feedback_check_person_already_shipped.md` — grep the author before
writing an entry) matches on names. The author of the reshare is an organisation,
*Hard Problems*; the author of the review is a person, *Daniel Burka*. A grep for
either name finds nothing of the other. The rule was followed and could not have
worked.

**3. Why did that condition exist?** Every duplicate guard in the repo was built
to the shape of the duplicate that produced it. `findDuplicateSourceUrls` and
`findSameTypeDuplicates` both compare `source_url` as a string, because the
duplicates that prompted them shared a URL exactly. "Same work, two URLs" was a
shape that had not happened yet, so nothing covered it.

**4. Why was it not already prevented?** Nothing read the archive for
relationships *between* records. The archive was treated as a text store —
something to check a blockquote against (`quote_integrity.py`) or a URL against
(`check_source_urls.py`) — and both of those index one record at a time. A
reshare is a fact about a pair.

**5. Why does the system allow that class of thing?** Because a guard that reads
a data file reports only its failures, so a guard that is reading nothing looks
exactly like a guard that is finding nothing. `check_source_urls.py` has indexed
`linkedinUrl` since 2026-11-04 and would have gone on passing if harvestapi
renamed the field. The same blindness that hid the quote gate at 2.9% coverage
while it exited 0 (`2026-10-28-the-quote-gate-verified-three-percent.md`) applies
to every archive-backed check, and had not been generalised past the one case.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | Duplicate entry and its card deleted; the Hard Problems reshare folded into Burka's entry as its first `source_urls` item, labelled as the publisher's announcement | fix | shipped |
| 2 — the local condition | The new check keys on activity ids, not names, so a publisher↔author mismatch cannot hide it. The name-grep rule stays, but is no longer the thing standing between this and the timeline | check | shipped |
| 3 — the process | `findReshareDuplicates()` in `src/lib/source-url-integrity.ts`: resolves each entry's source activity id through the reshare map before comparing, and ignores `type` because a publisher's announcement is often filed under a different one. Six tests in `tests/source-url-integrity.test.ts` pin it with the real activity ids | test | shipped |
| 4 — why it wasn't caught | `reshareMap()` in `scripts/lint-entries.ts` reads `repost.linkedinUrl` across the whole raw archive and feeds the check from the pre-commit hook. Proven against the live archive, not only the fixture: the map holds 94 pairs, including 7523410060706725888 → 7523409771211780096, and replaying the deleted entry against it fires | mechanism | shipped |
| 5 — the system | The check prints `Reshare index: N pair(s) from M raw archive file(s)` on every run, and **fails** when the archive has files but the index is empty — the one shape that cannot be a true negative. A renamed actor field now breaks the build instead of quietly disabling the guard | structural change | shipped |

## A note on the first run

The check's first run against the repo produced two failures, both naming Carol
Van Den Hende's post as a duplicate of Daniel Sharp's and Andrew Corcoran's
endorsements. All three were wrong. Sharp's and Corcoran's `source_url` is a
comment permalink — `/feed/update/urn:li:activity:<PARENT>?commentUrn=…` — which
embeds the *parent post's* id, and Van Den Hende's post reshared that same parent.
Three people's words under one post, read as one source three times.

This is the identical trap `check_source_urls.py` fell into on 2026-11-04, when
indexing comment permalinks made 33 correct URLs look fabricated. Two
implementations, two languages, same bug, three days apart —
`memory/feedback_one_rule_one_implementation.md` warned that a guard copied into a
second language diverges, and what actually happened is worse: it converged on the
same defect independently. The shared fact is that **a LinkedIn comment permalink
is not an identifier for the post it links to**, and it is now written down in
both places with a test on the TypeScript side.

## Where the check can fire

`data/archive/` is gitignored (`.gitignore:41`), so the reshare index exists only
on this machine. In GitHub Actions `rawCount` is 0, the empty-index failure
correctly does not trigger, and the check does nothing. That is the right side of
the trade — entries are written locally, the pre-commit hook runs locally, and the
archive is deliberately local-only — but it means the review bot cannot catch this
class and should not be assumed to. Said out loud here because a guard that runs
in one place and not another is exactly the kind of thing that gets remembered as
"we check for that".

## Open items

None. All five rows shipped.
