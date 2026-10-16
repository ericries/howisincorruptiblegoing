import { describe, it, expect } from 'vitest';
import {
  looksFabricated,
  findDuplicateSourceUrls,
  SHARED_CANONICAL_URLS,
} from '../src/lib/source-url-integrity';

// On 2026-10-16 an entry was written in a batch with the placeholder
// source_url ".../activity-7515320000000000000-xxxx" because the real URL was
// not to hand. It was caught by eye before commit — but a fabricated citation
// is indistinguishable from a real one at review time, and nothing in the
// pipeline would have stopped it. These are the guards.

describe('looksFabricated', () => {
  it('rejects the exact placeholder shape that nearly shipped', () => {
    expect(
      looksFabricated('https://www.linkedin.com/posts/gaurangpatel_the-ai-conference-2026-activity-7515320000000000000-xxxx')
    ).toBeTruthy();
  });

  it('rejects xxxx / yyyy / placeholder / example tokens', () => {
    for (const u of [
      'https://www.linkedin.com/posts/activity-1234-xxxx',
      'https://example.com/post',
      'https://www.example.org/a',
      'https://site.com/PLACEHOLDER',
      'https://site.com/TODO',
    ]) {
      expect(looksFabricated(u), u).toBeTruthy();
    }
  });

  it('rejects a LinkedIn activity id padded with improbable trailing zeros', () => {
    // real ids are 19 densely-varied digits; 7515320000000000000 is invented
    expect(looksFabricated('https://www.linkedin.com/posts/x_y-activity-7515320000000000000-AbCd')).toBeTruthy();
  });

  it('accepts the real URLs currently on the timeline', () => {
    for (const u of [
      'https://www.linkedin.com/posts/activity-7515475837362790400-VuUo',
      'https://www.linkedin.com/posts/mfors_nacdsummit-corporategovernance-boarddirectors-activity-7516142759548715008-b3XK',
      'https://x.com/rgmcgrath/status/2110007672141484035',
      'https://www.youtube.com/watch?v=xvFZKSRUxdA',
      'https://www.goodreads.com/review/show/9018046023',
      'https://time.com/article/2026/05/27/why-corporate-corruption-is-so-common/',
      'https://incorruptible.co',
    ]) {
      expect(looksFabricated(u), u).toBeFalsy();
    }
  });

  it('does not trip on a legitimate round number elsewhere in the URL', () => {
    expect(looksFabricated('https://www.inc.com/inc5000/2026/100-fastest')).toBeFalsy();
  });
});

describe('findDuplicateSourceUrls', () => {
  const mk = (id: string, source_url: string) => ({ file: `${id}.json`, source_url });

  it('flags two entries built on the same article', () => {
    // the real case: three Thought Economics entries on one URL, two of them
    // near-identical, unnoticed for five days
    const dups = findDuplicateSourceUrls([
      mk('a', 'https://thoughteconomics.com/eric-ries/'),
      mk('b', 'https://thoughteconomics.com/eric-ries/'),
      mk('c', 'https://other.com/x'),
    ]);
    expect(dups).toHaveLength(1);
    expect(dups[0].url).toBe('https://thoughteconomics.com/eric-ries/');
    expect(dups[0].files.sort()).toEqual(['a.json', 'b.json']);
  });

  it('ignores URLs that are legitimately shared by many entries', () => {
    // incorruptible.co is the book's own page, used as the canonical source by
    // 55 launch-era entries; the Amazon reviews page by milestones and readers
    const entries = SHARED_CANONICAL_URLS.flatMap((u, i) => [
      mk(`x${i}`, u),
      mk(`y${i}`, u),
    ]);
    expect(findDuplicateSourceUrls(entries)).toHaveLength(0);
  });

  it('is clean when every entry has its own source', () => {
    expect(
      findDuplicateSourceUrls([mk('a', 'https://a.com'), mk('b', 'https://b.com')])
    ).toHaveLength(0);
  });

  it('ignores entries with no source_url', () => {
    expect(
      findDuplicateSourceUrls([mk('a', ''), mk('b', '')])
    ).toHaveLength(0);
  });
});
