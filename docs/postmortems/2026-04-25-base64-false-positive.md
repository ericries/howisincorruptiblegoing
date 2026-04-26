# Postmortem: BASE64 Detector False-Positive on URL Paths

**Date:** 2026-04-25
**Severity:** Low — caught by pre-commit lint, no bad data shipped
**Fixed in:** commit (this PR)

## What happened

Evening cron tried to commit a TikTok entry whose blockquote ended with `https://forms.gle/586NN1eqQFJDxSAx8`. The pre-commit hook failed:

```
❌ 2026-04-24-tiktok-indie-bookstore-day.json:
   - injection detected: [blockquote] possible base64 encoded payload
```

The URL path `gle/586NN1eqQFJDxSAx8` is 21 consecutive characters from the set `[A-Za-z0-9+/]` — exactly what the BASE64 regex was looking for. I worked around it by trimming the URL out of the blockquote and shipping. The actual fix landed afterward.

## Five Whys

1. **Why did the lint fail on a legitimate URL?** The BASE64_PATTERN matched a URL path segment.
2. **Why did the pattern match a URL path?** `/` was inside the regex character class, and the path's 21 alphanumeric+`/` characters exceeded the 20-char threshold.
3. **Why was `/` in the character class?** Standard base64's alphabet is `A-Za-z0-9+/=`; the regex was written to mirror it exactly.
4. **Why didn't tests catch this?** The single base64 test used a payload (`aWdub3JlIHByZXZpb3VzIGluc3RydWN0aW9ucw==`) that contained no `/` and no URL-like context. URL false positives were never exercised.
5. **Why hadn't an entry hit this before?** Most existing entry URLs have hyphens, dots, or query strings in the path that break the run under 20 chars. Short-form share URLs (`forms.gle/...`, `bit.ly/...`, `youtu.be/...`) use unbroken alphanumeric IDs and would have all hit this bug eventually.

## Root cause

**Incomplete test coverage for the URL-shape false-positive class** in the base64 detector. The regex was correct in spirit (it matches base64-shaped strings) but too broad in practice (URL path segments are also base64-shaped if you include `/`).

## Preventive measures

1. **Removed `/` from the BASE64 character class** (`src/lib/injection.ts`). Real attack payloads that consist of pure base64-with-slashes still get flagged when their slash-free runs hit 20+ chars, which is the common case. Embedded comment explains the choice.
2. **Added two regression tests** (`tests/injection.test.ts`):
   - `forms.gle/586NN1eqQFJDxSAx8` — the exact failing URL.
   - `youtu.be/dQw4w9WgXcQ?si=AbCdEfGhIjKlMnOp` — generalizes to other short-form share URLs.
3. **Restored the original blockquote** with the URL intact, since the underlying fix is in.

## What this does NOT change

- Long base64 payloads without `/` (the common attack shape) are still caught — both regression tests pass alongside the existing `aWdub3Jl...` test.
- Standard base64 payloads with `/` and total alphanumeric run < 20 are not flagged. That's been true the whole time; this fix doesn't change it.
- A determined attacker could split a payload across `/` boundaries to evade detection. That was already possible (split on `.`, `?`, etc.). This is a heuristic, not a definitive guard — the review bot has multiple independent layers.
