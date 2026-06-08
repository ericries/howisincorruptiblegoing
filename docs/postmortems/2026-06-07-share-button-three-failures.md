# 2026-06-07 — Share button: three failure modes from one buggy first design

## What broke (user reported, in order)

On Chrome / macOS, the share button shipped in `92bd84a` exhibited three behaviors:

1. **Some buttons did nothing** when clicked.
2. **Some popped up a truncated (not fully visible) share dialog.**
3. **Some triggered the macOS native share sheet.**

Plus a fourth bug discovered alongside the first three: the quote-card image was rendering as a hero on the timeline *and* the textual content below was rendering the same quote, causing visible duplication.

## Five whys for each failure

### A. "Some buttons did nothing"

1. **Why did the button do nothing?** `navigator.share()` was called and on Chrome/macOS desktop it either silently surfaced an empty/minimal sheet or was dismissed without visible effect, leaving the user with no feedback.
2. **Why did `navigator.share()` get called?** Because `canShareFiles` evaluated to true and there was a `cardSrc`, the first-pass code path took the native-share branch unconditionally.
3. **Why was `canShareFiles` true on desktop Chrome?** Because Chrome 89+ exposes `navigator.share` and `navigator.canShare({ files })` on macOS desktop too. The API exists; the UX is just bad.
4. **Why didn't the code gate to mobile in the first place?** I conflated "API exists" with "this is the right UX path." Web Share API is a mobile-first pattern; on desktop it's a confusing dead end.
5. **Why did I conflate them?** I didn't read the platform conventions — I treated feature detection as sufficient for UX selection. Feature detection answers *can*, not *should*.

### B. "Truncated share dialog"

1. **Why was the popover truncated?** It was rendered with `position: fixed`, but the bounding box was scoped to its nearest **containing-block** ancestor — which was the timeline row, not the viewport.
2. **Why wasn't the viewport the containing block?** Because `.timeline-row` had `animation: cardEnter 0.5s ease both`. `animation-fill-mode: both` keeps the final keyframe state applied indefinitely, and the final keyframe sets `transform: translateY(0)`. Any non-`none` transform creates a new containing block for descendant `position: fixed` elements (CSS spec, "Fixed positioning containing block").
3. **Why does a `translateY(0)` transform create a containing block?** Because the CSS spec treats *any* applied transform value (including the no-op identity) as "the element has a transform applied" — used by browsers to enable GPU-layer compositing and to scope fixed-positioned descendants.
4. **Why didn't I catch this in the original design?** I assumed `position: fixed` meant "relative to viewport" without checking the containing-block rules.
5. **Why is this a recurring class of bug?** Containing-block rules for fixed/absolute positioning are subtle. Any of `transform`, `will-change`, `filter`, `contain: paint`, or `perspective` on an ancestor will silently re-scope `position: fixed` descendants. Reading "position: fixed" as "viewport-relative" is a heuristic that breaks in exactly this situation.

### C. "Triggered the native share action" (sometimes)

1. **Why did some buttons trigger native share?** Same as bug A — `canShareFiles` was true on Chrome/macOS, so the `navigator.share()` branch fired. The "did nothing" vs "triggered native" distinction was just whether the user perceived the macOS sheet as appearing at all.
2. (Same chain as A from here on.)

### D. "Duplicate image rendered above some entries"

1. **Why duplicate content?** The quote-card image rendered as a hero at the top of the card, and the textual body below rendered the same quote as `standard__quote`. The user saw the quote twice.
2. **Why did both render?** I had set `entry.image = "/images/cards/<id>.png"` and let the timeline's normal hero-image branch take over, then added Astro logic to *also* render the title text below since the hero overlay was suppressed for cards. I never suppressed the body's `standard__quote`.
3. **Why didn't I suppress the body's blockquote when there was a card hero?** I treated the quote card as a decorative hero, expecting readers to scan visually. I didn't realize the body content was effectively a verbatim duplicate.
4. **Why didn't I notice?** I never browsed the deployed site after shipping. I inspected the generated PNGs (they looked great) and shipped without rendering the page in a browser.
5. **Why didn't I browse-test?** Convenience plus overconfidence — I treated "the cards look right" as "the entries render right." Those are different questions; I conflated them.

## What we changed (in `8e8e73c`)

- **Touch-only gating** for the native-share path. `canShareFiles` now requires `maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches`. Desktop Chrome (any platform) gets the popover, not the native sheet.
- **Portal pattern** for the popover. The menu DOM lives inside the entry at SSR for accessibility/JS-free fallback, then JS moves it to `<body>` on open. That escapes any transform-containing-block ancestor, including `.timeline-row`'s `cardEnter both`.
- **No card-as-hero treatment.** Quote cards (`/images/cards/*`) are no longer rendered as timeline heroes — they exist only as share-asset PNGs (`og:image` on permalink pages, the share button's native-share payload, and the permalink page's main visual). The textual card body is the single source of timeline content.
- **Icon-only action pair** at the lower-right of every entry: permalink (chain-link icon, copies URL) and share (iOS up-arrow-out-of-box icon).

## Lessons (locked into tests)

The tests in `tests/share-button.test.ts` codify these so the next person who edits the share button can't silently re-introduce a regression:

| Test | Lesson |
|---|---|
| `gates native share to touch devices` | Feature detection ≠ UX selection. The source must check `pointer: coarse` or `maxTouchPoints`. |
| `portals the popover to <body> on open` | `position: fixed` is meaningless if an ancestor has any transform. Verify the portal call. |
| `.timeline-row uses animation-fill-mode: both` | Document the containing-block trap as an invariant; any popover descendant must portal out. |
| `quote-card images are NOT rendered as timeline heroes` | Decorative card hero + textual body = duplicate content. Cards stay share-only. |
| `every standard card variant wires the entry actions` | The original first-pass only wired the standard variant; cinematic/award/quote-only/featured-review were missing. |
| `permalink page sets og:image to the entry's card` | Foundation of the share story; if this breaks, recipient unfurls go blank. |
| `entry actions are icon-only (no "Share" text)` | Per user direction, the buttons stay subtle icons. |

## Follow-up: iOS Safari still didn't open the native sheet (2026-06-08)

After the 8e8e73c fix, a user on iOS reported that tapping the share icon still didn't open the native iOS share widget — the popover appeared instead. Fifth why:

1. **Why didn't iOS get the native sheet?** Because `canShareFiles` was returning `false` on iOS, so the click handler fell through to the popover path.
2. **Why did `canShareFiles` return false?** Because the feature-detection probe was `navigator.canShare({ files: [new File([new Blob()], 'probe.png', { type: 'image/png' })] })`.
3. **Why did that probe return false on iOS Safari?** Because Safari validates the *contents* of the file passed to `canShare({ files })`, not just the MIME type. An empty Blob with a claimed `image/png` MIME doesn't match a real PNG header, so Safari rejected the probe.
4. **Why didn't I catch this in testing?** I only checked that `canShare` existed; I didn't verify Safari accepted my specific probe payload. I treated the API's permissive behavior on Chrome as universal.
5. **Why is this a recurring class of bug?** Same as Bug A — conflating "feature detected" with "feature works for my exact call site." `canShare` is a *capability query*: its answer depends on what you ask it about. An empty Blob is a degenerate query that some implementations reject.

**Fix (this commit):** drop the upfront file-API probe entirely. `canNativeShare` only checks `isTouchDevice && typeof navigator.share === 'function'`. The real `canShare({ files: [actualFile] })` check happens inside `nativeShare()` against the fetched PNG. If that returns false — or if anything else goes wrong (fetch fails, user-activation dropped across the await) — the function transparently falls back to `navigator.share({ url, title, text })`, which still opens the OS native sheet.

**Test invariants added (`tests/share-button.test.ts`):**

- `does NOT probe canShare with an empty Blob` — regression catch for this exact bug; re-introducing `new File([new Blob()], …)` fails the test.
- `falls back to URL-only share when the file path fails` — `nativeShare()` source must contain BOTH the file-attached share AND a URL-only share, so iOS users always get the OS sheet even when file attach fails.
- `uses the touch signal as a precondition for native share` — updated to check the new `canNativeShare` definition instead of the removed `canShareFiles`.

Mutation-verified: reintroducing the empty-Blob probe via sed makes the dedicated test fail; reverting passes.

## Follow-up: Chrome/macOS native share was URL-only (2026-06-08)

After the iOS-empty-Blob fix, a user on Chrome/macOS reported the native sheet now opens — but only with the URL, no card attached. Sixth why:

1. **Why did Chrome/macOS share URL-only?** Because the code still gated the file-attached share behind `if (!navigator.canShare || navigator.canShare({ files: [file] }))`, and on Chrome/macOS that check returns `false` for an `image/png` file.
2. **Why does Chrome/macOS canShare return false for PNG files?** Chrome's implementation of `canShare({ files })` on desktop is conservative — it doesn't always accurately predict whether the underlying macOS Sharing widget will accept the file. It returns false for cases where the actual `navigator.share({ files })` call would succeed.
3. **Why was I gating on canShare at all?** Defensive programming: ask permission before attempting. The intent was to fall back to URL-only when files weren't supported.
4. **Why didn't the defensive check work?** Because `canShare`'s spec contract — "return true iff share will succeed" — is broken in practice. Chrome's implementation is too conservative; some platforms accept file shares without canShare's blessing.
5. **Why is this a recurring class of bug?** Same chain as bugs A and the iOS fix: I trusted a capability query to predict the answer, when the only reliable answer is to attempt the action. Capability queries are HINTS, not contracts. For Web Share API, the cleanest pattern is "try, catch, fall back" — let the platform decide.

**Fix (this commit):** drop the upfront `canShare({ files })` check around the file-share attempt. The function now just calls `navigator.share({ files: [file], url, title, text })` directly. If the platform rejects, we catch the error, fall through to `navigator.share({ url, title, text })`, and the user gets the URL-only share they had before. If the platform accepts (which Chrome/macOS actually does for PNG, despite canShare's pessimism), the recipient gets the card image. Failed file-share attempts that reject synchronously don't consume user activation, so the URL-only fallback still runs in the same click.

**Test invariant added:** `does NOT gate the file share on canShare (Chrome/macOS lies — 2026-06-08 follow-up)` scans the `nativeShare` body and fails if a `canShare({…files…}) {` gate appears between the File construction and `navigator.share({ files })`. Mutation-verified.

**Pattern lesson for future Web Platform APIs:**

> Capability queries (`canX`, `is*Supported`, etc.) are hints, not contracts. When they're cheap to retry, prefer "try and catch" over "ask first" — the runtime behavior is the ground truth, not the prediction.

## Preventive measures

- **CSS containing-block invariant test.** Whenever I add a `position: fixed` popover to a component that lives inside `.timeline-row`, I either portal it to `<body>` or remove `animation-fill-mode: both` on the row. The test in `tests/share-button.test.ts` enforces this for the share menu specifically.
- **Build-time smoke test.** `tests/share-button.test.ts` reads the rendered `dist/index.html` and counts that every timeline entry's HTML block contains the `data-share` action group. Build-time output is the canonical record of what users see.
- **Postmortem promotes "verify in DOM, not source"** from `feedback_verify_in_dom.md` — the body-quote duplication is exactly the pattern that memory warns about, and I still made it. Reinforcing the rule by writing this postmortem.
