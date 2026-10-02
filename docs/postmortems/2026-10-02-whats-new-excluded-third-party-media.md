# Postmortem: a 167K-subscriber interview was skipped, then silently barred from What's New

**Date:** 2026-10-02
**Impact:** A major podcast appearance went unshipped for two days. Separately, **72 entries — every podcast, interview and press piece where Eric is the quoted speaker, including a New York Times article — were structurally unable to appear in the What's New sidebar.** No wrong data was published; the cost was missed and invisible coverage.

## What happened

On 2026-09-30 the LinkedIn keyword scan surfaced a FounderCoHo post with structured "Takeaways" about Eric and *Incorruptible*. I judged it an aggregator with 2,052 followers and skipped it. On 10-01 the YouTube scan returned the same thing from the other side: a **68-minute original interview on a 167,000-subscriber channel**, with Eric on the one word he regrets in *The Lean Startup*. I shipped it.

Then at sidebar curation I went to feature it and found it could never render: `index.astro` filtered out any entry whose `blockquote_source` starts with `"Eric Ries"`.

## Five whys — part 1: why was it skipped?

1. **Why skip it?** I judged it low-reach.
2. **Why?** I used the follower count in front of me: 2,052, the LinkedIn account's.
3. **Why was that the number in front of me?** The item arrived via the LinkedIn keyword scan, which reports the *LinkedIn author's* audience — not the audience of the platform the content lives on.
4. **Why didn't I check the destination?** No step in the process said to. "Reach" was implicitly whatever number the scan handed me.
5. **Root cause:** reach was judged on the surface where the item was *found*, not the surface where the content *lives*. For a cross-posted item those differ — here by 80×.

Contributing: the post's "Takeaways:" formatting reads like aggregator behaviour, so the shape of the post reinforced the wrong conclusion. It was in fact a promo for their own episode.

## Five whys — part 2: why was it unfeatureable?

1. **Why couldn't it be featured?** `index.astro:27` dropped it.
2. **Why?** The filter excluded `blockquote_source.startsWith('Eric Ries')`.
3. **Why does that filter exist?** What's New is for third-party momentum, so Eric posting on his own channels should not appear.
4. **Why did it catch third-party press?** Because in a podcast or an interview, the quoted speaker *is* Eric. The field was being used as a proxy for "whose content is this" when it actually records "who said the quoted words."
5. **Root cause:** one field conflated **speaker** with **venue**. Self-amplification needs both to be Eric; the filter only ever tested one.

Measured before the fix: the old rule excluded **89** entries, of which only **17** were genuine self-amplification. The other **72** were third-party coverage — 51 podcasts, 15 media, 2 events, an endorsement.

## Fix

`src/lib/entries.ts` gains two exported helpers, with 21 tests in `tests/self-amplification.test.ts`:

- `isEricVenue(url)` — is this one of Eric's own surfaces? Anchored path matching (`/in/eries`, `/posts/eries_`, `/ericries/`, `/@ericriesactual`) plus `incorruptible.co` / `theleanstartup.com`, so a third party whose handle merely contains "eries" doesn't match.
- `isSelfAmplification(entry)` — `speakerIsEric && isEricVenue(source_url)`.

`index.astro` now filters on `isSelfAmplification`. Still excluded: the 17 TikToks and LinkedIn posts that are Eric on Eric's channel. Now eligible: the FounderCoHo interview, the Business Leader podcast, the NYT piece, and 69 others.

Note `src/pages/people.astro:65` uses a similar `startsWith('Eric Ries')` check on `attribution` — that one is correct and was left alone. It excludes Eric from the *people* directory, which is about who the person is, not about provenance.

## Prevention

1. **Judge reach at the destination, not the referrer.** Before skipping any item that points to content on another platform, resolve the link and check that platform's audience. A LinkedIn post promoting a YouTube episode tells you nothing about the episode's reach.
2. **Record the audience on media entries.** `type_metadata.audience` (e.g. `"167K YouTube subscribers"`) so the number is captured at ship time and curation does not have to re-derive it. Convention, not lint-enforced — backfilling 50+ existing podcast entries is not worth it.
3. **When a filter uses a field as a proxy, say so and test it.** The comment above the old filter described the *intent* ("excludes Eric's own posts") accurately while the *code* did something broader. The intent was never wrong; the encoding was.
