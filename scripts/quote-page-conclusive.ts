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
/**
 * Decode the HTML entities a reader never sees as entities.
 *
 * visibleText stripped tags and stopped there, so a WordPress page rendering
 * "you&rsquo;re" produced text that could never match "you're". Ten entries —
 * every one a blog, Substack or Goodreads page, which are the formats that
 * emit entities — were reported as composites, the gravest verdict this
 * checker has. LinkedIn and X are skipped by the live checker, which is why
 * the cluster read as a vintage rather than as a format.
 */
function decodeEntities(text: string): string {
  const named: Record<string, string> = {
    amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
    rsquo: '\u2019', lsquo: '\u2018', rdquo: '\u201d', ldquo: '\u201c',
    mdash: '\u2014', ndash: '\u2013', hellip: '\u2026', bull: '\u2022',
    middot: '\u00b7', eacute: '\u00e9', egrave: '\u00e8', agrave: '\u00e0',
    ccedil: '\u00e7', uuml: '\u00fc', ouml: '\u00f6', auml: '\u00e4',
    szlig: '\u00df', ntilde: '\u00f1', iacute: '\u00ed', oacute: '\u00f3',
    aacute: '\u00e1', uacute: '\u00fa', deg: '\u00b0', trade: '\u2122',
    copy: '\u00a9', reg: '\u00ae', euro: '\u20ac', pound: '\u00a3',
  };
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&([a-z]+);/gi, (m, n) => named[n.toLowerCase()] ?? m);
}

export function visibleText(raw: string): string {
  if (!raw) return '';
  return decodeEntities(raw
    .replace(/<(script|style|noscript|template)\b[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' '))
    .replace(/\s+/g, ' ')
    // A tag becomes a space so a block boundary still separates words, but an
    // INLINE element butts against punctuation: "<em>The Lean Startup</em>,"
    // would otherwise read as "The Lean Startup ,", which no reader sees. That
    // artefact failed a sound Porchlight entry on 2026-10-31.
    .replace(/\s+([,.;:!?%)\]}])/g, '$1')
    .replace(/([(\[{$])\s+/g, '$1')
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
