/**
 * Did we actually receive the document, or just a 200?
 *
 * A quote missing from a page only refutes an entry if the page arrived. A JS
 * shell, cookie wall or captcha returns 200 with no article body. On
 * 2026-10-28 Goodreads returned a 13,234-character shell for a sound review
 * entry and verify-quotes.ts reported "QUOTE NOT FOUND on page" — a false
 * accusation that would have blocked the commit.
 *
 * A false FAIL is worse than a false pass: it blocks good work and trains
 * everyone to pass --no-verify.
 *
 * This mirrors `is_conclusive` in scripts/review_bot/verify_quotes.py. The two
 * must agree; the pre-commit hook caught them disagreeing the moment only one
 * had been fixed. See docs/postmortems/2026-10-28-the-quote-gate-verified-three-percent.md
 */

/** Below this a response cannot plausibly be an article, review or post body. */
export const MIN_PLAUSIBLE_CHARS = 1200;

/** A shorter quote prefix matches too much markup to prove anything. */
export const MIN_PREFIX_SIGNAL = 25;

/**
 * Text a reader would see: script/style bodies and tags removed.
 *
 * Both signals below must be read from THIS, not from raw markup. A YouTube
 * watch page is hundreds of KB of HTML, so a length floor on the raw string
 * always passes, and it carries the channel name in metadata while the
 * transcript the quote came from is nowhere in the document. On 2026-10-30
 * that produced a confident FAIL against a sound entry.
 */
export function visibleText(raw: string): string {
  if (!raw) return '';
  return raw
    .replace(/<(script|style|noscript|template)\b[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function fold(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim();
}

/**
 * Two signals count, either alone: the author's name appears, or enough of the
 * quote's opening appears that we are plainly on the right text. Length alone
 * is not a signal — walls can be long — but being far too short rules it out.
 */
export function isConclusive(
  page: string,
  quote: string,
  attribution: string | null | undefined
): boolean {
  page = visibleText(page);
  if (!page || page.length < MIN_PLAUSIBLE_CHARS) return false;

  const low = page.toLowerCase();
  const name = (attribution ?? '').trim().toLowerCase();
  if (name && low.includes(name)) return true;

  const prefix = fold(quote ?? '').slice(0, 40);
  return prefix.length >= MIN_PREFIX_SIGNAL && fold(page).includes(prefix);
}
