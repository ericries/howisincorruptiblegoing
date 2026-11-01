/**
 * Does the blockquote appear at the source page?
 *
 * Extracted from verify-quotes.ts on 2026-10-31 so it can be tested. Two
 * defects lived here, both producing false FAILs:
 *
 *   1. It did not know the elision convention. SCAN-PROTOCOL.md §5 requires a
 *      deliberate trim to be marked ` … `, and scripts/repair_elisions.py
 *      writes exactly that; quote_integrity.py verifies such a quote segment by
 *      segment. This checker normalised … to ... and searched for the whole
 *      string, so an elided quote missed, matched on its opening, and was
 *      reported as "PARTIAL — composite risk". The mark that exists to
 *      distinguish an honest cut from a composite was read as the composite.
 *      23 entries carry one.
 *
 *   2. It matched against raw HTML. isConclusive was taught to read visible
 *      text on 2026-10-30 after a YouTube shell produced a confident FAIL; the
 *      matcher one function away was left as it was, so a quote spanning a <p>
 *      boundary could not be found on a page that plainly contained it.
 *
 * The composite must stay catchable, so a segment that is absent — or present
 * but out of source order — still fails.
 */

import { visibleText } from './quote-page-conclusive';

/** The marker for a deliberate cut, in either spelling, with surrounding space. */
const CUT = /\s+(?:…|\.\.\.)\s+/;

export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[‘’“”]/g, "'")   // smart quotes → straight
    .replace(/—/g, '--')                       // em dash
    .replace(/–/g, '-')                        // en dash
    // Folded AFTER the cut split in findQuoteInPage, so a spaced ' … ' is
    // already gone and only an author's own trailing-off ellipsis reaches
    // here. quote_integrity.py folds it too, and the shared corpus holds the
    // case that caught this side missing it.
    .replace(/…/g, '...')                      // ellipsis
    .replace(/\s+/g, ' ')                           // collapse whitespace
    .trim();
}

export interface QuoteMatch {
  found: boolean;
  partial: boolean;
  matchedChars: number;
}

/**
 * Segments of an elided quote must appear in the page in source order, each
 * one after the last. Returns the number of characters matched before giving
 * up, so the caller can distinguish "the opening is real and the rest is not"
 * from "none of this is here".
 */
function matchSegments(segments: string[], page: string): QuoteMatch {
  let cursor = 0;
  let matched = 0;
  for (const segment of segments) {
    const at = page.indexOf(segment, cursor);
    if (at === -1) {
      // Some of it was real. That is the composite signature when the quote
      // was never marked as cut, and a bad trim when it was.
      return { found: false, partial: matched > 0, matchedChars: matched };
    }
    cursor = at + segment.length;
    matched += segment.length;
  }
  return { found: true, partial: false, matchedChars: matched };
}

export function findQuoteInPage(quote: string, pageHtml: string): QuoteMatch {
  const page = normalize(visibleText(pageHtml));
  const segments = quote
    .split(CUT)
    .map((s) => normalize(s))
    .filter((s) => s.length > 0);

  if (segments.length === 0) return { found: false, partial: false, matchedChars: 0 };

  if (segments.length > 1) return matchSegments(segments, page);

  const nq = segments[0];
  if (page.includes(nq)) return { found: true, partial: false, matchedChars: nq.length };

  // A contiguous quote that misses: report how much of its opening is real, so
  // a composite reads differently from a quote that is simply not here.
  for (const n of [60, 30]) {
    if (nq.length >= n && page.includes(nq.slice(0, n))) {
      return { found: false, partial: true, matchedChars: n };
    }
  }
  return { found: false, partial: false, matchedChars: 0 };
}
