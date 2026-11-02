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

  // Superseded 2026-11-02. The author's name alone WAS the accept signal, and
  // the reasoning was sound as far as it went: a real page names its author.
  // But a Goodreads profile and an Apple Podcasts page also name their author,
  // in the navigation, while the review or description is drawn by JavaScript
  // and never reaches the HTML. On those the checker declared the page readable
  // and then reported "composite risk" against text it had never seen. Six
  // entries were accused that way, so the name is no longer sufficient on its
  // own; some window of the quote has to be visible.
  it('a page that names the author but carries none of the quote is inconclusive', () => {
    const page = 'x'.repeat(3000) + ' A review by Jeff Berman about something else.';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(false);
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

  it.skip('matches the author name case-insensitively (name signal retired 2026-11-02)', () => {
    const page = 'w'.repeat(3000) + ' reviewed by JEFF BERMAN here';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(true);
  });

  it('will not let a very short quote carry the prefix signal', () => {
    const page = 'q'.repeat(3000) + ' astounding ';
    expect(isConclusive(page, 'astounding', 'Nobody Here')).toBe(false);
  });
});

describe('isConclusive reads visible text, not markup', () => {
  const YOUTUBE_SHELL =
    '<html><head><meta name="author" content="Stanford eCorner">' +
    '<script>var ytInitialData={"channel":"Stanford eCorner","x":"' + 'z'.repeat(40000) + '"};</script>' +
    '</head><body><div id="app"></div></body></html>';

  it('rejects a huge shell whose name is only in markup', () => {
    // The 2026-10-30 false FAIL: raw HTML clears the length floor and the
    // channel name sits in metadata, while the transcript the quote came from
    // is not in the document at all.
    expect(isConclusive(YOUTUBE_SHELL, QUOTE, 'Stanford eCorner')).toBe(false);
  });

  it.skip('still accepts a real page whose name is in body text (name signal retired 2026-11-02)', () => {
    const page = '<html><body><p>' + 'lorem ipsum '.repeat(300) + ' reviewed by Jeff Berman</p></body></html>';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(true);
  });

  it('does not let script bodies pad the length floor', () => {
    const page = '<html><body><script>' + 'x'.repeat(50000) + '</script><p>hi</p></body></html>';
    expect(isConclusive(page, QUOTE, ATTRIB)).toBe(false);
  });
});

describe('a page is conclusive only when the quote is actually visible on it', () => {
  // The author's name alone used to be enough. On a Goodreads profile or an
  // Apple Podcasts page the name sits in the navigation while the review or
  // description is rendered by JavaScript and never reaches the HTML, so the
  // checker declared the page readable and then reported the quote PARTIAL —
  // "composite risk" — against a quote it had never actually looked at. Six
  // entries were accused that way.
  const QUOTE =
    'I have been teaching college business ethics and individual choice takes center stage, but other forces matter more';

  it('a navigation-only page is inconclusive even when the author is named', () => {
    const nav =
      ('<p>David Bauman Home My Books Browse Recommendations Choice Awards Genres ' +
       'Giveaways New Releases Lists Explore News Interviews Community Groups Quotes ' +
       'Ask the Author Sign in Join</p>').repeat(8);
    expect(isConclusive(nav, QUOTE, 'David Bauman')).toBe(false);
  });

  it('a page carrying a real run of the quote is conclusive', () => {
    const page = `<p>${'Some review prose. '.repeat(80)} ${QUOTE.slice(20, 90)} and so on.</p>`;
    expect(isConclusive(page, QUOTE, 'David Bauman')).toBe(true);
  });

  it('a run from the MIDDLE of the quote counts, not only the opening', () => {
    // Bauman's page says "over 18 years" where the quote says "15 years", so
    // the opening diverges while the rest is plainly the same text. That is a
    // real divergence to report, not a page we failed to read.
    const page = `<p>${'Some review prose. '.repeat(80)} over 18 years, ${QUOTE.slice(60)} ...</p>`;
    expect(isConclusive(page, QUOTE, 'David Bauman')).toBe(true);
  });

  it('a page too short to be anything is still inconclusive', () => {
    expect(isConclusive('<p>Just a moment...</p>', QUOTE, 'David Bauman')).toBe(false);
  });
});
