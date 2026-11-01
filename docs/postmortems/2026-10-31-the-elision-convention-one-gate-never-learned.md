# The elision convention reached one quote gate and not the other, so every honestly-trimmed quote read as a composite

**Date:** 2026-10-31
**Found by:** the evening scan, writing the first elided blockquote whose source page an anonymous fetch can actually read. Nobody asked; it surfaced because `verify-quotes.ts` blocked the commit with a confident FAIL against an entry I had just verified by hand against the publisher's own transcript.

## What happened

`SCAN-PROTOCOL.md` §5 requires a deliberately trimmed blockquote to mark the cut
with ` … `, and `scripts/repair_elisions.py` writes exactly that. The offline
gate, `scripts/quote_integrity.py`, verifies such a quote segment by segment
(`_match_segmented`, added 2026-10-28 with the elision convention itself).

The live gate, `scripts/verify-quotes.ts`, never learned it. Its matcher folded
`…` to `...` and then searched for the **whole blockquote as one string**. An
elided quote contains a marker the source does not, so the search always missed.
It then fell through to a prefix check and reported:

```
❌ 2026-10-28-bryan-cantrill-books-in-the-box-vi.json — QUOTE NOT FOUND on page
```

**23 of 884 entries carry a marked cut.** The mark that exists to distinguish an
honest trim from a composite was read, by one of the two gates, as the composite
signature. For entries on fetchable pages the verdict was `PARTIAL — composite
risk`; the one that surfaced it fell to `QUOTE NOT FOUND` because of a second
defect in the same function.

That second defect: `findQuoteInPage` matched against **raw HTML**, not visible
text. `isConclusive` was taught to read visible text on 2026-10-30 after a
YouTube shell produced a confident FAIL; the matcher one call away in the same
file was left as it was, so a quote spanning a `<p>` boundary could not be found
on a page that plainly contained it.

Both are false FAILs. The existing note in `quote-page-conclusive.ts` states the
stakes exactly: *"A false FAIL is worse than a false pass: it blocks good work
and trains everyone to pass `--no-verify`."*

Measured after the fix, on the same entry and page: `1 pass, 0 warn, 0 FAIL`.

### Verifying the fix found a third defect

A fix to a gate is worth no more than the check on it, so old and new matchers
were run against **the same fetch** of every entry whose source page an
anonymous request can read: 97 conclusive pages, 15 verdicts moved.

| move | n | reading |
|---|---|---|
| `PARTIAL -> PASS` | 7 | false FAILs, now verified |
| `NOTFOUND -> PASS` | 5 | false FAILs, now verified |
| `NOTFOUND -> PARTIAL` | 2 | still failing, but the opening is now located in the document |
| `PASS -> PARTIAL` | 1 | **a regression introduced by the fix** |

The regression was `2026-05-26-porchlight-new-releases`, and both verdicts were
wrong. `visibleText` replaces every tag with a space so that a block boundary
still separates words — but an inline element butts against punctuation, so

    creator of <em>The Lean Startup</em>, comes a bold

extracted as `The Lean Startup , comes`, which no reader ever sees. The entry is
sound; the extraction was not.

The old `PASS` was not right either: the page's rendered body does not match it
*in raw HTML* at all, and the old matcher had been passing it by matching a
**JSON-LD blob in the markup** — precisely what `visibleText` was introduced on
2026-10-30 to stop. A verdict that happened to be green for a reason unrelated
to the entry.

Fixed in `visibleText` rather than in the matcher, so the offline gate — which
reads stored plain text and never sees a tag — is unaffected and the two stay in
parity. `tests/quote-match.test.ts` covers an inline tag against a comma,
against a full stop, and the block boundary that must still separate words.

## Five whys

**1. Why did it happen?** `verify-quotes.ts` searched for the blockquote as a
single string. An elided quote cannot match that way, by construction.

**2. Why was that possible?** The elision convention was introduced on
2026-10-28 in `quote_integrity.py` and in the protocol, and the other gate was
not touched. The two were treated as one gate because they normally agree.

**3. Why did that condition exist?** They share no code. `quote_integrity.py`
(offline, against a captured source text) and `verify-quotes.ts` (live, against
a fetched page) were written at different times for different problems, each
with its own `normalize()` and its own matching. A convention added to one is
invisible to the other *by construction*, not by oversight.

**4. Why was it not already prevented?** This is the **third** instance of the
same shape in four days: `is_conclusive` added to Python and not TypeScript
(2026-10-28); both copies reading raw HTML (2026-10-30); the elision convention
today. Each of the first two was fixed by copying the change across. Copying
across is the instance fix — it repairs the divergence in front of you and
leaves the mechanism that produces divergences untouched.

**5. Why does the system allow that class of thing?** Nothing asserted the two
gates agree. The pre-commit hook runs them in sequence and compares their
verdicts never. A divergence could only be noticed when one of them happened to
fail loudly on a hand-written entry — which is to say, by luck. This is the same
shape as the quote gate that reported passes and was read as coverage: a number
that was never measured against the thing it was taken to mean.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | `scripts/quote-match.ts` splits on the cut marker and matches segments in source order; an absent or out-of-order segment still fails, so the composite stays catchable | fix | shipped |
| 2 — the local condition | `tests/quote-match.test.ts` — 14 hand-written cases: segments in order, out of order, an invented segment, the `...` spelling, an element boundary, a script body, and an inline tag against punctuation | test | shipped |
| 3 — the process | the live gate no longer owns a matcher. `verify-quotes.ts` imports `quote-match.ts`, which imports `visibleText` from `quote-page-conclusive.ts`; the local `normalize`/`findQuoteInPage` pair is deleted, so the TypeScript side has one implementation rather than two | mechanism | shipped |
| 4 — why it wasn't caught | `data/quote-match-cases.json`, a corpus of (quote, text, expected) cases loaded by **both** `tests/quote-match.test.ts` and `scripts/test_quote_match_cases.py`. A convention taught to one language and not the other now fails the other language's tests. It earned itself immediately: adding an ellipsis-folding case caught the TypeScript side still missing a fold the Python side had | mechanism | shipped |
| 5 — the system | the cross-language corpus above is the structural change available at this size. Collapsing the two gates into one implementation is the real fix and is **declined**: they answer different questions against different inputs — offline against a stored capture, live against a fetched page — and merging them would couple the thing that still works to the thing that is network-dependent and flaky. The corpus buys the agreement without the coupling | structural change | declined |

## Open items

- **57 entries FAIL the live gate across the full corpus** (`41 pass, 194 warn,
  57 FAIL, 592 skip`, measured 2026-10-31). The pre-commit hook only checks
  *changed* entries, so this backlog has never blocked anything and has never
  been looked at. It is not yet known how many are stale URLs, how many are
  paywalls that clear `isConclusive`, and how many are real. **Nobody has
  triaged this.** The count is the finding; the causes are not established.
- A full-corpus live run takes minutes and is run by nothing on a schedule, so
  that number is not tracked and could drift either way unobserved.
