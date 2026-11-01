# The quote gate's 33 failures were carried as a number for four days; a third of them were the checker

**Date:** 2026-11-01
**Found by:** triaging a backlog I had reported three times without reading. The count was in two postmortems and a scan report as "33 failures remain needing human judgement" and "57 entries fail the live gate, untriaged — nobody has looked."

## What happened

Since 2026-10-28 the offline quote gate had stood at **33 failures**, and the
live gate at **57**. Both numbers were reported, carried forward, and listed as
open items. Neither was examined.

Reading them produced a different picture.

**All 33 offline failures were LinkedIn captures.** One platform, 100% — a
systematic cause, not 33 independent mistakes. Reading the divergence bytes
rather than the verdicts showed three distinct populations:

| cause | n | real? |
|---|---|---|
| quote style — published `'financial gravity'` where the post wrote `"financial gravity"` | | no |
| dash style — an em dash where the post had a plain hyphen | | no |
| Unicode-styled text — the post sets a line in mathematical bold (`𝗗𝗼𝗻'𝘁 𝗹𝗲𝘁 𝗰𝗲𝗿𝘁𝗮𝗶𝗻𝘁𝘆 𝗿𝗲𝗽𝗹𝗮𝗰𝗲 𝗰𝘂𝗿𝗶𝗼𝘀𝗶𝘁𝘆`), the quote transcribes plain letters | 11 total | no |
| tidied punctuation — a truncation closed with a fabricated period, or a comma promoted to a sentence boundary | 3 | yes |
| a substituted word | 1 | yes |
| genuine composites, reordering, paraphrase | 18 | yes, and still open |

`normalise` folded curly quotes to straight and em dashes to `--`, which is
where the drift happened to be when those folds were written. It did not fold
single-against-double quotes, dash-against-hyphen, or Unicode styling. Each
unfolded difference produced a `PARTIAL` verdict — and `PARTIAL` is defined in
this repo as *"the composited-quote signature"*. **The checker was accusing
sound entries of fabrication on typography.**

The one real fabrication was `2026-07-05-andrew-bond-well-health-canada`,
published since July: *"tools of institution building that meet the
**seriousness** of the considerable lift ahead"* where the source says
**significance**. It sat inside the same list as the eleven false ones, and
the list was never opened.

The live gate's 57 told a different story again: **zero entries fail both
gates**, five have dead source URLs, and six fail live while verifying
offline — the page drifted, the entry is sound.

After the fixes: **33 → 22 failures, 367 → 381 verified, coverage 44.8% →
45.6%.** The 22 that remain involve reordering or paraphrase;
`repair_elisions.py` refuses all of them, correctly.

## Five whys

**1. Why did the gate report 33 failures?** `normalise` folded some typographic
variation and not the rest, so a quote differing only in quote style, dash
style or Unicode styling read as a content divergence.

**2. Why was the fold incomplete?** Each fold had been added in response to a
specific case already seen. The set of folds was a history of past incidents
rather than a model of how text drifts.

**3. Why did that matter so much?** Because the verdict does not say "these
strings differ"; it says `PARTIAL`, which the codebase documents as the
composited-quote signature. An imprecise checker is tolerable. One whose
imprecision is published as an accusation of fabrication is not — and it is the
same failure in the opposite direction as the false `FAIL` that
`quote-page-conclusive.ts` exists to prevent.

**4. Why was it not caught for four days?** The failures were summarised as a
count. A count is quotable in a report and carries no evidence, so "33
failures" could be repeated three times without anyone meeting a single one.
I wrote "nobody has triaged this" in a report and then did not triage it.

**5. Why does the system allow that class of thing?** Nothing made the evidence
travel with the verdict. The tool printed the entry id, the first 110
characters of the quote, and the URL — everything except the one thing that
distinguishes a checker bug from a content bug, which is *where the two texts
part*. A summary that omits its evidence will be read as a conclusion.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | quote style, dash style and Unicode styling (NFKC) now fold on both sides; the four genuinely misquoted entries repaired, including the substituted word live since July | fix | shipped |
| 2 — the local condition | a corpus case per fold class in `data/quote-match-cases.json`, including one asserting that a **substituted word still fails** — the folds must not be able to grow into a checker that passes everything | test | shipped |
| 3 — the process | `quote_integrity.divergence()` reports the longest verbatim prefix and the next span on each side, backed off to a word boundary; the failure output now prints it. A failure cannot be read without its evidence | mechanism | shipped |
| 4 — why it wasn't caught | the 20 milestone entries whose "blockquote" is a synthesised badge label (`#1 New Release in Startups`) are waived with a stated reason, so the uncapturable count means "needs a capture" rather than "contains something uncheckable by construction". `data/no-capture-waivers.json` existed for this and had never been used | mechanism | shipped |
| 5 — the system | renaming the verdicts so they state an observation rather than a cause was considered and **declined**: `PARTIAL` naming the composite signature is what makes the gate legible, and the evidence shipped at level 3 fixes the actual defect — the reader now sees the divergence next to the name, so the name cannot stand in for the finding | structural change | declined |

## Open items

- **22 entries still fail the offline gate**, each needing per-entry judgement:
  reordered spans, paraphrase, and quotes assembled from passages that are not
  in source order. `repair_elisions.py` refuses them all, which is the correct
  behaviour. Several will change what the entry says, so they are not mine to
  decide alone.
- **Five entries have dead `source_url`s**, four pointing at the Amazon
  product-reviews page which now 404s. Two were recovered verbatim from
  `data/amazon-reviews/`; `2026-05-26-reader-lisa-brennan-jobs` predates the
  first local snapshot and cannot be recovered without a fresh paste.
- 481 entries still have no captured source text at all.
