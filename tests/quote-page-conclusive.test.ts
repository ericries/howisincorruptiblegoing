import { describe, it, expect } from 'vitest';
import { isConclusive } from '../scripts/quote-page-conclusive';

/**
 * A 200 response is not proof we received the document.
 *
 * This guard was written for the Python CI verifier on 2026-10-28 and NOT for
 * the TypeScript one, and the pre-commit hook caught the omission immediately:
 * committing a sound Goodreads entry produced "QUOTE NOT FOUND on page" from
 * verify-quotes.ts while quote_integrity.py passed it against the captured
 * source text. Goodreads serves a 13,234-character JS shell with no review
 * body. The quote was not absent; the page was never delivered.
 *
 * A false FAIL is worse than a false pass here: it blocks good entries and
 * teaches everyone the gate is noise.
 */

const QUOTE =
  'we have fetishized shareholder returns at the cost of other stakeholders';
const ATTRIB = 'Jeff Berman';

describe('isConclusive', () => {
  it('rejects a tiny shell page', () => {
    expect(
      isConclusive('<html><head></head><body><div id="app"></div></body></html>', QUOTE, ATTRIB)
    ).toBe(false);
  });

  it('accepts a page that names the author', () => {
    const page = 'x'.repeat(3000) + ' A review by Jeff Berman about something else.';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(true);
  });

  it('accepts a page carrying the quote opening, so composites stay catchable', () => {
    const page = 'y'.repeat(3000) + ' ' + QUOTE.slice(0, 40) + ' and then invented words.';
    expect(isConclusive(page, QUOTE, 'Someone Else')).toBe(true);
  });

  it('rejects a long cookie wall with neither signal', () => {
    const page = 'Please enable JavaScript to continue. '.repeat(200);
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(false);
  });

  it('rejects an empty page', () => {
    expect(isConclusive('', QUOTE, ATTRIB)).toBe(false);
  });

  it('tolerates a missing attribution', () => {
    const page = 'z'.repeat(3000) + ' ' + QUOTE.slice(0, 40);
    expect(isConclusive(page, QUOTE, null)).toBe(true);
  });

  it('matches the author name case-insensitively', () => {
    const page = 'w'.repeat(3000) + ' reviewed by JEFF BERMAN here';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(true);
  });

  it('will not let a very short quote carry the prefix signal', () => {
    const page = 'q'.repeat(3000) + ' astounding ';
    expect(isConclusive(page, 'astounding', 'Nobody Here')).toBe(false);
  });
});
