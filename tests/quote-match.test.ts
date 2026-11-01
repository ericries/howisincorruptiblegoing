import { describe, it, expect } from 'vitest';
import { findQuoteInPage } from '../scripts/quote-match';

/**
 * The live checker must understand the two conventions the protocol mandates.
 *
 * 1. A deliberate trim is marked ` … ` (SCAN-PROTOCOL.md §5, and what
 *    scripts/repair_elisions.py writes). quote_integrity.py verifies such a
 *    quote segment by segment. verify-quotes.ts never learned the convention:
 *    it normalised … to ... and looked for the whole string, so an elided
 *    quote missed, matched on its first 60 characters, and was reported as
 *    "PARTIAL — composite risk" — the deliberate cut read as the composite
 *    signature it exists to distinguish itself from. 23 entries carry one.
 *
 * 2. Signals must be read from VISIBLE text, not raw markup. That was fixed in
 *    isConclusive on 2026-10-30 and left unfixed in the matcher one function
 *    away, so a quote split across <p> tags could not be found on the page that
 *    plainly contained it.
 *
 * Both failures are false FAILs, which block good entries and teach everyone to
 * reach for --no-verify.
 */

const PAGE = `
  <html><body>
    <p>Bryan Cantrill:</p>
    <p>every company that does some of these things like setting yourself up as a
       public benefit corporation and so on, feels like they're doing something
       completely bonkers that no one has ever conceived of before.</p>
    <p>And this book helps to stitch some of this together into like actually,
       lots of actually people are doing things like this. It's not just you and
       the book has been has found, I think it's a great book.</p>
  </body></html>`;

describe('findQuoteInPage — elided quotes', () => {
  it('verifies an "A … B" quote whose segments are both on the page, in order', () => {
    const quote =
      "every company that does some of these things like setting yourself up as a " +
      "public benefit corporation and so on, feels like they're doing something " +
      "completely bonkers that no one has ever conceived of before. " +
      "… people are doing things like this. It's not just you";
    expect(findQuoteInPage(quote, PAGE).found).toBe(true);
  });

  it('handles three segments', () => {
    const quote =
      'every company that does some of these things … And this book helps to ' +
      "stitch some of this together … It's not just you";
    expect(findQuoteInPage(quote, PAGE).found).toBe(true);
  });

  it('rejects an elided quote whose segments are out of source order', () => {
    const quote =
      "It's not just you … every company that does some of these things like " +
      'setting yourself up as a public benefit corporation';
    expect(findQuoteInPage(quote, PAGE).found).toBe(false);
  });

  it('rejects an elided quote with an invented segment — the composite must stay catchable', () => {
    const quote =
      'every company that does some of these things like setting yourself up as a ' +
      'public benefit corporation … and that is why we sold the company to private equity';
    const r = findQuoteInPage(quote, PAGE);
    expect(r.found).toBe(false);
    expect(r.partial).toBe(true);
  });

  it('accepts the "..." spelling of the cut as well as the ellipsis character', () => {
    const quote =
      "every company that does some of these things ... It's not just you";
    expect(findQuoteInPage(quote, PAGE).found).toBe(true);
  });
});

describe('findQuoteInPage — reads visible text, not markup', () => {
  it('finds a quote that spans an element boundary', () => {
    // The source sentence is broken across two <p> tags plus indentation.
    const quote =
      "completely bonkers that no one has ever conceived of before. And this book " +
      'helps to stitch some of this together';
    expect(findQuoteInPage(quote, PAGE).found).toBe(true);
  });

  it('does not match text hidden in a script body', () => {
    const page =
      '<html><body><script>var x = "the mission is a marketing exercise";</script>' +
      '<p>unrelated prose</p></body></html>';
    expect(findQuoteInPage('the mission is a marketing exercise', page).found).toBe(false);
  });
});

describe('findQuoteInPage — unelided quotes behave as before', () => {
  it('verifies a contiguous quote', () => {
    expect(findQuoteInPage("It's not just you", PAGE).found).toBe(true);
  });

  it('still reports a partial match as the composite signature', () => {
    const quote =
      'every company that does some of these things like setting yourself up as a ' +
      'public benefit corporation and then immediately abandons it for a quick exit';
    const r = findQuoteInPage(quote, PAGE);
    expect(r.found).toBe(false);
    expect(r.partial).toBe(true);
  });

  it('reports neither found nor partial when the quote is simply absent', () => {
    const r = findQuoteInPage('a sentence that appears nowhere in the document', PAGE);
    expect(r.found).toBe(false);
    expect(r.partial).toBe(false);
  });
});

/**
 * The shared corpus. data/quote-match-cases.json is loaded by BOTH this suite
 * and scripts/test_quote_match_cases.py, so a convention taught to one
 * language's matcher and not the other fails the other's tests. That is the
 * mechanism this postmortem bought: the elision marker reached the Python gate
 * on 2026-10-28 and this one on 2026-10-31, and nothing in between noticed.
 */
import cases from '../data/quote-match-cases.json';

describe('shared quote-match corpus', () => {
  for (const c of cases.cases) {
    it(c.name, () => {
      const r = findQuoteInPage(c.quote, c.text);
      expect(r.found).toBe(c.expect === 'found');
    });
  }
});

/**
 * Stripping a tag must not invent a space the reader never sees.
 *
 * Found 2026-10-31 by comparing the old and new matchers over the same fetch of
 * every entry's source page: 2026-05-26-porchlight-new-releases moved PASS ->
 * PARTIAL. The page is sound and the sentence is its rendered body text. The
 * old matcher "passed" it by matching a JSON-LD blob in the markup — the exact
 * thing visibleText exists to stop — while the new one failed it because
 * replacing every tag with a space turns
 *
 *     creator of <em>The Lean Startup</em>, comes a bold
 *
 * into "creator of The Lean Startup , comes a bold". Inline elements butt
 * against punctuation; the space before the comma is an artefact of extraction,
 * not something a reader sees.
 */
describe('findQuoteInPage — stripping inline tags leaves no stray space', () => {
  const PAGE =
    '<p><strong>From Eric Ries, creator of <em>The Lean Startup</em>, comes a bold ' +
    'and urgently needed rethink of how organizations are built</strong></p>';

  it('matches across an inline tag that sits against a comma', () => {
    const quote =
      'From Eric Ries, creator of The Lean Startup, comes a bold and urgently ' +
      'needed rethink of how organizations are built';
    expect(findQuoteInPage(quote, PAGE).found).toBe(true);
  });

  it('matches across an inline tag that sits against a full stop', () => {
    const page = '<p>the structure is the <em>whole point</em>. Nothing else holds.</p>';
    expect(findQuoteInPage('the structure is the whole point. Nothing else holds.', page).found)
      .toBe(true);
  });

  it('still separates words that a block boundary genuinely divides', () => {
    // <p>one</p><p>two</p> is "one two", never "onetwo".
    expect(findQuoteInPage('one two', '<p>one</p><p>two</p>').found).toBe(true);
    expect(findQuoteInPage('onetwo', '<p>one</p><p>two</p>').found).toBe(false);
  });
});
