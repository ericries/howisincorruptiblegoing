# The live quote gate reported fifteen entries as composites, and six of them were pages it had never read

**Date:** 2026-11-02
**Found by:** the legacy-summary rewrite. Touching 240 entries pulled them into the pre-commit hook's changed set, and the live checker — which only ever sees entries somebody edits — read them for the first time in months. Fifteen failed. Not one was found by the gate doing its job on a schedule.

## What happened

`verify-quotes.ts` failed fifteen entries. Eleven carried the verdict **PARTIAL
match — composite risk**, which is the gravest thing this system says: it means
the opening of a quote is real and the rest is not, the signature of words
assembled from different places and attributed to one person.

They were not fifteen bad quotes. They were four different things:

| cause | n | what it was |
|---|---|---|
| HTML entities never decoded | — | `you&rsquo;re` could not match `you're` |
| spaces around dashes not folded | 2 | quote `" - "`, page `"-"` |
| page unreadable, accused anyway | 6 | visible text was navigation; the review never loaded |
| genuine defect | 7 | composites, a fabricated quote, an edited source |

Only the last column was real.

## Five whys

**1. Why were sound entries reported as composites?** `visibleText` stripped
tags and stopped. It never decoded HTML entities, so a WordPress page rendering
`you&rsquo;re` produced text that could not match `you're`, and the matcher
reported the quote as diverging partway through.

**2. Why did that go unnoticed for months?** The live checker runs only on
entries a commit touches, and it skips LinkedIn and X — 62% of the timeline.
What remains is blogs, Substacks, Goodreads and company sites: exactly the
formats that emit entities. So the defect was invisible until something touched
a large number of old non-social entries at once, which had never happened.

**3. Why did it accuse pages it could not read?** `isConclusive` accepted a page
if the author's name appeared anywhere in it. On a Goodreads profile or an Apple
Podcasts page the name sits in the navigation while the review or description is
drawn by JavaScript and never reaches the HTML. The gate read a nav bar,
concluded it was on the right page, and failed the quote against text it had
never seen.

**4. Why was the same normalisation wrong in two places?** Because there are two
implementations. `quote-page-conclusive.ts` folded space-before-punctuation;
`quote_integrity.py` did not. `quote-match.ts` folded dash characters but not
the spaces around them. Each gap was found separately, by hand, by reading
output. `data/quote-match-cases.json` exists precisely to stop this and was
added on 2026-10-31 — three cases short of catching any of it.

**5. Why does the system allow that class of thing?** Because a checker that
cries wolf costs nothing until someone believes it. Eleven "composite risk"
verdicts stood for months against entries that were fine, and the only reason
they were not acted on is that nobody looked. The design principle the quote
gate already states — never trust an LLM-reported quote — has no counterpart
saying **the gate must not accuse when it cannot read**. It was free to fail
closed on a page it had failed to fetch, and failing closed looks exactly like
finding a fabrication.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | `visibleText` decodes numeric and named HTML entities before matching. Marty Cagan's entry went from FAIL to verified on this alone | fix | shipped |
| 2 — the blind spot | the fifteen are repaired and verified: four marked cuts and composites rewritten to contiguous source text, one source that had genuinely changed re-captured, one "blockquote" that was never a quote replaced with the publication's own sentence | fix | shipped |
| 3 — accusing unread pages | `isConclusive` no longer accepts a page on the author's name. It requires a window of the quote's own text, from anywhere in it, to be visible — positive evidence the content loaded. A page carrying none of it is reported INCONCLUSIVE, not FAILED. Six entries moved from accusation to honest abstention | mechanism | shipped |
| 4 — two implementations | eight new cases in `data/quote-match-cases.json`, which both the TypeScript and Python suites load: entity decoding, space-before-punctuation, space-inside-brackets, and dash spacing in both directions. Each was red on at least one side before the fix | mechanism | shipped |
| 5 — the system | the rule now has a name: **a gate must not accuse when it cannot read.** Encoded as the conclusiveness test rather than as prose, so the next page format that fails to render is abstained from rather than convicted. **Declined**: running the live checker over all 890 entries on a schedule. It is network-bound and slow, it would re-fetch stable pages daily for nothing, and the thing that actually needed fixing was the checker's willingness to convict — a nightly run of a gate that cries wolf produces 890 false verdicts instead of 11 | structural change | shipped |

## What the real defects were

Worth recording separately, because four of them are the failure the gate exists
to catch and it did catch them, once it could read the page:

- **Leah Solivan** — a composite of four separated passages, whose opening
  sentence appears nowhere on the page at all.
- **GeekWire** — the "blockquote" was a paraphrase written in our own voice,
  never a quote. Replaced with GeekWire's own sentence.
- **Unshackled Ventures** — "Purpose and performance are designed as one
  system." was a subordinate clause lifted from a different paragraph and
  promoted into a standalone sentence.
- **Dilip Goswami** — "Eric illustrates through a remarkable range of stories …
  that" belongs to a sentence ending "is corruption", and had been grafted onto
  the front of a separate passage.
- **Steve Blank** and **Henny Portman** — real quotes with unmarked cuts, now
  marked with ` … `.
- **David Bauman** — not a defect at all. He revised his review from "for 15
  years" to "for over 18 years" after it was captured. Entry and capture both
  refreshed to what he says now.

## One mistake made while fixing it

Re-capturing Bauman's revised review, I wrote only the quote span into the
capture file and discarded the rest of the page. The drift checker caught it
within the minute — his summary's "Regis University, Denver" suddenly read as
unsourced, because the evidence for it had just been deleted. **A capture is
evidence, and trimming it to the part you are currently interested in destroys
evidence.** Re-captured in full, 14,416 characters. The capture now carries a
note saying what changed and why, which the original refresh should have done
in the first place.

## Open items

- Five entries now report INCONCLUSIVE rather than verified: Lift Economy, the
  Investor Relations podcast on Apple Podcasts, Ryan Honeyman's Goodreads
  review, CNBC, and the SOSV summit page. Their quotes pass against the
  captures taken at ship time, and the live pages render their content with
  JavaScript, so nothing anonymous can confirm them. That is the honest answer
  rather than a verdict, but it does mean five entries no live check can ever
  reach.
- `2026-05-28-ryan-honeyman-bcorp-handbook-goodreads` is still a duplicate of
  `2026-05-27-ryan-b-corp-handbook-author-goodreads` — the same review by the
  same person a day apart, with the real captured text on the earlier one. A
  merge, not a repair, and Eric's call.
