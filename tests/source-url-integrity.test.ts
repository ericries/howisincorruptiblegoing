import { describe, it, expect } from 'vitest';
import {
  looksFabricated,
  findDuplicateSourceUrls,
  findSameTypeDuplicates,
  SHARED_CANONICAL_URLS,
  findReshareDuplicates,
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

/**
 * Same-type duplicates are a failure, not a warning.
 *
 * Mixed types sharing a URL is legitimate — an event and a reaction to it, a
 * milestone and the review page it counts. Two entries of the SAME type on one
 * URL is a duplicate every time it has occurred: three Thought Economics media
 * entries on one interview, and a Goodreads review shipped twice on 2026-10-20
 * because the "fresh" check compared datasets instead of the timeline. The
 * warning surfaced that one, but only after the entry and its card existed.
 */
describe('findSameTypeDuplicates', () => {
  it('fails two entries of the same type on one url', () => {
    const dups = findSameTypeDuplicates([
      { file: 'a.json', type: 'media', source_url: 'https://x.test/eric' },
      { file: 'b.json', type: 'media', source_url: 'https://x.test/eric' },
    ]);
    expect(dups).toHaveLength(1);
    expect(dups[0].files).toEqual(['a.json', 'b.json']);
  });

  it('allows an event and a reaction to cite the same post', () => {
    expect(findSameTypeDuplicates([
      { file: 'a.json', type: 'event', source_url: 'https://x.test/p' },
      { file: 'b.json', type: 'reaction', source_url: 'https://x.test/p' },
    ])).toEqual([]);
  });

  it('allows shared canonical urls even for one type', () => {
    expect(findSameTypeDuplicates([
      { file: 'a.json', type: 'endorsement', source_url: 'https://incorruptible.co' },
      { file: 'b.json', type: 'endorsement', source_url: 'https://incorruptible.co' },
    ])).toEqual([]);
  });

  it('ignores trailing-slash differences', () => {
    expect(findSameTypeDuplicates([
      { file: 'a.json', type: 'review', source_url: 'https://x.test/r' },
      { file: 'b.json', type: 'review', source_url: 'https://x.test/r/' },
    ])).toHaveLength(1);
  });

  it('ignores entries with no source_url', () => {
    expect(findSameTypeDuplicates([
      { file: 'a.json', type: 'review', source_url: '' },
      { file: 'b.json', type: 'review', source_url: undefined },
    ])).toEqual([]);
  });
});

// On 2026-11-06 an entry was written for "Hard Problems publishes a review of
// Incorruptible" whose source_url was a LinkedIn post that turned out to be a
// RESHARE of Daniel Burka's own post — and Burka's review was already on the
// timeline as 2026-11-03-daniel-burka-rare-to-recommend-a-business-book.
// findSameTypeDuplicates compares source_url literally, so two URLs pointing at
// one piece of writing read as two sources. The raw archive knows: the reshare
// record carries repost.linkedinUrl. Resolve through it before comparing.
describe('findReshareDuplicates', () => {
  const HARD_PROBLEMS =
    'https://www.linkedin.com/posts/hardproblems_incorruptible-by-eric-ries-activity-7523410060706725888-lrPq';
  const BURKA_ORIGINAL =
    'https://www.linkedin.com/posts/dburka_incorruptible-by-eric-ries-activity-7523409771211780096-h0kb';

  it('catches the Hard Problems reshare against the Burka original', () => {
    const groups = findReshareDuplicates(
      [
        { file: 'a.json', source_url: BURKA_ORIGINAL },
        { file: 'b.json', source_url: HARD_PROBLEMS },
      ],
      new Map([['7523410060706725888', '7523409771211780096']])
    );
    expect(groups).toHaveLength(1);
    expect(groups[0].files.sort()).toEqual(['a.json', 'b.json']);
  });

  it('catches it when the original is cited in source_urls rather than source_url', () => {
    const groups = findReshareDuplicates(
      [
        { file: 'a.json', source_url: 'https://www.hardproblems.com/articles/incorruptible-eric-ries',
          source_urls: [{ url: BURKA_ORIGINAL }] },
        { file: 'b.json', source_url: HARD_PROBLEMS },
      ],
      new Map([['7523410060706725888', '7523409771211780096']])
    );
    expect(groups).toHaveLength(1);
  });

  it('allows a reshare whose original is not on the timeline', () => {
    expect(
      findReshareDuplicates(
        [{ file: 'b.json', source_url: HARD_PROBLEMS }],
        new Map([['7523410060706725888', '7523409771211780096']])
      )
    ).toEqual([]);
  });

  // The first run flagged two entries whose source_url was a COMMENT permalink:
  // /feed/update/urn:li:activity:<PARENT>?commentUrn=... embeds the parent post's
  // id, so three commenters under one post all look like they cite that post.
  // Carol Van Den Hende's entry reshared that same parent — which made two real
  // endorsements read as duplicates of hers. A comment is its own utterance.
  it('ignores a comment permalink, which carries its parent post id', () => {
    const PARENT = '7520227988064575488';
    const RESHARE = '7520305758748545024';
    expect(
      findReshareDuplicates(
        [
          { file: 'sharp.json', source_url: `https://www.linkedin.com/feed/update/urn:li:activity:${PARENT}?commentUrn=urn%3Ali%3Acomment%3A%28activity%3A${PARENT}%2C7520475506878889984%29` },
          { file: 'carol.json', source_url: `https://www.linkedin.com/posts/carolvandenhende_x-activity-${RESHARE}-QSA3` },
        ],
        new Map([[RESHARE, PARENT]])
      )
    ).toEqual([]);
  });

  it('allows two unrelated entries', () => {
    expect(
      findReshareDuplicates(
        [
          { file: 'a.json', source_url: BURKA_ORIGINAL },
          { file: 'b.json', source_url: 'https://www.linkedin.com/posts/x_y-activity-7000000000000000001-AbCd' },
        ],
        new Map()
      )
    ).toEqual([]);
  });

  it('does not flag an entry against itself when it cites both reshare and original', () => {
    expect(
      findReshareDuplicates(
        [{ file: 'a.json', source_url: BURKA_ORIGINAL, source_urls: [{ url: HARD_PROBLEMS }] }],
        new Map([['7523410060706725888', '7523409771211780096']])
      )
    ).toEqual([]);
  });
});
