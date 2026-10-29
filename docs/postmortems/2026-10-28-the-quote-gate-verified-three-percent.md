# The quote gate verified 2.9% of entries and exited 0, because the hook advertised the way to switch it off

**Date:** 2026-10-28
**Found by:** Auditing the open item left by
[`2026-10-28-triage-archived-a-quarter-of-the-dataset.md`](2026-10-28-triage-archived-a-quarter-of-the-dataset.md),
which said other readers in the repo also stop at "the request succeeded". They
do. This is the third postmortem of the day and the most serious: the others
cost coverage of a social feed, this one is the guarantee the whole project
rests on.

## What happened

`CLAUDE.md` calls blockquote fidelity CRITICAL three times and names
`scripts/verify-quotes.ts` as the check. Measured across all 871 entries:

```
skip: verified:false      725
skip: LinkedIn             67
skip: endorsement blurb    52
skip: Twitter/X             2
ACTUALLY QUOTE-CHECKED     25     = 2.9%
```

It exits 0 on that. `Results: 25 pass, N warn, 0 FAIL, 846 skip` reads like
success.

The CI gate, `scripts/review_bot/verify_quotes.py`, has no `verified:false`
skip — but `fetch_page` returns `None` on any exception and `None` means
`WARN` + `continue`. 62% of entries cite LinkedIn or X, which no anonymous
fetch can read. Every one of them merged warned-but-unchecked.

And when a fetch *did* succeed, it could still be wrong in the other
direction: the live Goodreads page for a sound entry returns a **13,234-character
JS shell** with no review text, which the checker scored as `FAIL Quote NOT
found` — a false accusation against a good entry.

`verified: true` has not been set on anything since **June 2026**. Nothing in
the codebase writes it; nothing reads it except the skip.

## Five whys

**1. Why were 725 entries not quote-checked?**
`verify-quotes.ts` skipped every entry with `verified: false`, and the scanner
stamps `verified: false` on every entry it creates.

**2. Why does every new entry carry the flag that disables its own verification?**
Because the pre-commit hook told me to. Verbatim, in the failure message:
`echo "   Fix blockquotes to match source pages, or set verified: false."`
The documented remedy for a failing quote check was to disable the quote check
for that entry. An escape hatch printed in an error message is not an escape
hatch; it is the second option on a menu, and it is the cheap one.

**3. Why was that escape hatch needed often enough to become universal?**
Because the hook computed `CHANGED_ENTRIES` and then ran `verify-quotes.ts`
with **no arguments** — the script ignores argv and walks the whole directory.
Every commit re-fetched all 871 source pages over the network. `verified:
false` was the only lever that made committing bearable, so it became
load-bearing for speed, and its meaning drifted from "known unverifiable" to
"new".

**4. Why did nobody notice the gate had stopped gating?**
Nothing reported coverage. The output counts passes, warns and skips, and the
exit code depends only on failures — so a run that verified nothing was
indistinguishable from a run that verified everything. The same hole in two
directions: unreachable pages passed silently, and unparseable pages failed
loudly and wrongly. Both come from treating an HTTP 200 as the document.

**5. Why does this system keep shipping checks that can silently check nothing?**
Because every check here is written to answer "did I find a problem?" and none
is written to answer "how much did I actually look at?". That is the same root
as the two earlier postmortems today — an item cap that bound unseen, a read
that returned a quarter of a dataset. Coverage is never a first-class output,
so it decays silently, and the decay is invisible precisely because the tool
keeps reporting success on the shrinking remainder.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | The `verified: false` skip is deleted from `verify-quotes.ts`. "Nobody has confirmed this yet" is a reason to check an entry, not to wave it through | fix | shipped |
| 2 — the attractor | The hook no longer advertises the hatch. Its message now names the failure mode by number so the next person reads why it is not an option | fix | shipped |
| 3 — the pressure that created it | `verify-quotes.ts` honours file arguments and the hook passes `$CHANGED_ENTRIES`, so a commit checks the entries it touches instead of re-fetching 871 pages. The reason the hatch existed is gone | fix | shipped |
| 4 — why it wasn't caught | `scripts/quote_integrity.py` verifies blockquotes against the source text the scanner already captured — offline, instant, and the only check that works on auth-walled sources. It reports coverage every run (`checked N/M`) and takes a `--min-checked` floor so decay fails loudly. 28 tests. Added to the pre-commit hook ahead of the network check. The CI verifier now prints `verified N of M; K unreachable` and says plainly when it verified nothing | mechanism | shipped |
| 5 — the system | `isConclusive()` / `is_conclusive()`, shared by both verifiers, makes "I received a document" a precondition for refutation: a miss counts only when the author's name or enough of the quote's opening is present, so a JS shell can no longer convict a sound entry. Paired with `quote_integrity`'s six-valued verdict — where `NO_SOURCE`, `SOURCE_MISMATCH` and `MEDIUM_MISMATCH` are all distinct from pass — "I could not check this" can no longer collapse into "this is fine" anywhere in the quote path | structural change | shipped |

Verified by breaking it: grafting a plausible tail onto a real quote in
`2026-04-14-venky-goodreads-review` produces `quote PARTIAL in captured source`
and exit 1, which is the composited-quote signature the old checker rated a
warning. Restoring the file returns a clean exact match.

**The hook caught me fixing only half of it.** `is_conclusive` went into the
Python CI verifier first; committing this work then failed at the pre-commit
stage with `QUOTE NOT FOUND on page` from `verify-quotes.ts` on the very
Goodreads entry the guard was written for, while `quote_integrity.py` passed it.
Two verifiers, one guard, and the gate is only as good as the weaker. The guard
now lives in `scripts/quote-page-conclusive.ts` with 8 vitest cases mirroring
the 8 pytest cases, and both verifiers import it.

## What the checker found, and what it did not

First run reported **83 failures**. Both I opened were the checker being wrong,
so I did not report them as fabrications:

- **14 were `SOURCE_MISMATCH`** — the capture is keyed by entry id but holds a
  related url. Itamar Gilad's entry cites his article; the capture is his X post
  announcing it. Absence in the wrong document is not refutation.
- **69 were `MEDIUM_MISMATCH`** — all transcripts. A podcast url carries two
  bodies of text: the spoken audio and the written show notes. We capture the
  audio; blockquotes are often pulled from the blurb. "Eric shares powerful
  stories from companies like Costco, Cloudflare, and Anthropic" is episode
  copy, not speech. A transcript can confirm a quote and never refute one.

I tried a fuzzy token-overlap test to rescue the transcript cases and
**abandoned it**: real-but-lightly-cleaned quotes scored 0.15–1.00 while
deliberately mismatched controls scored 0.14–0.64. The distributions overlap
too much to threshold honestly, and a gate that guesses is worse than one that
abstains.

After both corrections: **163 entries verified against captured source, 0
failures** — 147 exact, 16 matching only after normalisation. Of those 16, 15
are newline joins, non-breaking spaces and styled Unicode in the source. One
was real byte drift — a straight apostrophe where Goodreads has a curly one, in
`2026-08-31-jeff-berman-goodreads-60-years-shareholder-fetish` — now repaired.

**No fabricated or composited quote was found.** That is the honest result of
this audit, and it is a weaker statement than it sounds: 708 entries still have
no capture to check against.

## Open items

**The forward gap is closed.** `quote_integrity.py --require-capture` runs in
the pre-commit hook against newly ADDED entries: a new entry carrying a
blockquote with no captured source text fails the commit. Saving the source
text was already a standing instruction (`memory/project_source_text_archive`);
it is now a mechanism, which is the distinction the 2026-10-21 postmortem was
about. Waivers live in `data/no-capture-waivers.json` and require a stated
reason — deliberately a committed file rather than a field on the entry,
because a field flip is exactly what `verified: false` was. The gate is scoped
to added files so that editing a legacy entry is not blocked by its own
history.

**The backlog is now half closed.** `scripts/backfill_source_text.py` recovers
captures cheapest-route-first: 8 from raw archives already on disk, 76 by plain
HTTP fetch with text extraction, 185 LinkedIn posts via
`apimaestro/linkedin-post-detail` for about $0.93. **Coverage went from 163 to
385 of 871 entries (18.7% -> 44.2%).**

486 entries still have none. 81 are genuinely unrecoverable and `--plan` names
each reason: incorruptible.co publishes 4 of its 55 blurbs, Amazon/Forbes/
USAToday return 403 to anonymous clients, NYT/FT are paywalled. The rest —
YouTube transcripts, X, TikTok, the remaining ~135 LinkedIn posts — are
tractable on the same routes and left for a later pass. **Open.**

**And the backfill found what the checker was built for: 14 composited
blockquotes**, built from real source spans in source order with the joins
invisible. `scripts/repair_elisions.py` marked each cut with an ellipsis, but
only where every segment is verbatim and in order; 33 remain that fragment past
the safety limits and need a person. **Open.**

The `verified` field is now vestigial: required by both validators and the TS
type, written only as `false`, read by nothing. Removing it touches 871 entries
and three schemas, so it was out of scope here. It is inert rather than
harmful now that the skip is gone. **Open.**
