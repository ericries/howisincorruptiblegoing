# Postmortem: base64 injection detector flagged a legitimate hashtag

**Date:** 2026-09-28
**Impact:** One valid entry (`2026-09-28-trent-wakenight-responsive-graphic-recording`) was blocked at lint time. No bad data shipped; the cost was a scan-cycle detour and a weaker blockquote than the source's best line.

## What happened

The morning scan shipped a graphic-recording entry whose blockquote quoted the source LinkedIn post verbatim, including its `#responsiveconference` hashtag. `scripts/lint-entries.ts` failed it with:

```
injection detected: [blockquote] possible base64 encoded payload
```

## Five whys

1. **Why did lint fail?** `detectInjection` reported a base64 payload in the blockquote.
2. **Why?** `BASE64_PATTERN = /[A-Za-z0-9+]{20,}={0,2}/` matched `responsiveconference` — exactly 20 characters.
3. **Why did a plain English word match a base64 pattern?** The rule keyed only on *alphabet* and *length*, never on whether the run actually looks encoded.
4. **Why was length alone thought sufficient?** The two prior regressions this rule was patched for (`forms.gle` short codes, YouTube IDs) were both fixed by narrowing the *alphabet* (dropping `/`), so length stayed the only other lever and nobody revisited it.
5. **Root cause:** the detector had no entropy-style signal. Any sufficiently long alphanumeric token — hashtag, slug, compound word — was indistinguishable from an encoded payload.

## Fix

`src/lib/injection.ts`: a 20+ char run is now flagged only if it mixes **uppercase, lowercase, and digits** — which base64 of any real payload does, and English hashtags do not. Implemented by scanning all runs (`/g` + `.some()`) rather than testing the string once, so a genuine payload elsewhere in the field is still caught even when a benign long token appears first.

Regression tests added in `tests/injection.test.ts` for both `#responsiveconference` (single-case) and `#BusinessForGoodRoundtable` (CamelCase, no digits). The existing true-positive test (`aWdub3JlIHByZXZpb3VzIGluc3RydWN0aW9ucw==`) still passes.

## Prevention

- The rule now needs a *reason* to fire, not just a length. Future long-token false positives should be fixed by adding signal, not by shortening the alphabet again.
- Every regression on this detector gets a named test in `tests/injection.test.ts`. Three such tests now exist (forms.gle, YouTube ID, hashtags).
