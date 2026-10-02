import { describe, it, expect } from 'vitest';
import { isEricVenue, isSelfAmplification } from '../src/lib/entries';

/**
 * "What's New" is for third-party momentum, so Eric posting on his own
 * channels is excluded. The original rule tested `blockquote_source` alone —
 * i.e. "is Eric the one being quoted?" — which also excluded every podcast,
 * every interview, and a New York Times piece, because in those the quoted
 * speaker is of course Eric. 72 legitimate third-party entries were barred.
 *
 * The distinction that actually matters is two facts, not one:
 *   speaker — who said the quoted words
 *   venue   — whose platform it appeared on
 * Self-amplification is BOTH being Eric. See
 * docs/postmortems/2026-10-02-whats-new-excluded-third-party-media.md
 */

const entry = (over: Record<string, unknown> = {}) => ({
  id: 'x', date: '2026-10-01', type: 'podcast',
  title: 't', summary: 's', blockquote: 'b',
  blockquote_source: 'Someone Else', source_url: 'https://example.com/x',
  ...over,
} as never);

// === venue detection ===

describe('isEricVenue', () => {
  it.each([
    ['https://www.linkedin.com/posts/eries_incorruptible-activity-7412', true],
    ['https://www.linkedin.com/in/eries/', true],
    ['https://www.tiktok.com/@ericriesactual/video/7691855992463674637', true],
    ['https://x.com/ericries/status/2104273631505248578', true],
    ['https://twitter.com/ericries/status/123', true],
    ['https://incorruptible.co', true],
    ['https://theleanstartup.com/book', true],
  ])('treats %s as an Eric-owned venue', (url, expected) => {
    expect(isEricVenue(url)).toBe(expected);
  });

  it.each([
    ['https://www.youtube.com/watch?v=2NtKUPkg3BM', false],
    ['https://www.nytimes.com/2026/07/25/business/grady-white-boats.html', false],
    ['https://www.linkedin.com/posts/lennyrachitsky_each-month-activity-75', false],
    ['https://www.linkedin.com/posts/hattie-moll-78352616_early-morning', false],
    ['https://podcasts.apple.com/us/podcast/incorruptible-with-eric-ries/id1', false],
    ['https://www.goodreads.com/review/show/8585404570', false],
  ])('treats %s as a third-party venue', (url, expected) => {
    expect(isEricVenue(url)).toBe(expected);
  });

  it('does not match a different person whose handle contains eries', () => {
    expect(isEricVenue('https://www.linkedin.com/posts/valeries_something')).toBe(false);
  });

  it('is safe on a missing url', () => {
    expect(isEricVenue(undefined)).toBe(false);
    expect(isEricVenue('')).toBe(false);
  });
});

// === the combined rule ===

describe('isSelfAmplification', () => {
  it('is true when Eric is quoted on his own channel', () => {
    expect(isSelfAmplification(entry({
      blockquote_source: 'Eric Ries on TikTok',
      source_url: 'https://www.tiktok.com/@ericriesactual/video/7691855992463674637',
    }))).toBe(true);
  });

  it('is FALSE for a podcast where Eric is the guest (the FounderCoHo case)', () => {
    expect(isSelfAmplification(entry({
      blockquote_source: 'Eric Ries on FounderCoHo',
      source_url: 'https://www.youtube.com/watch?v=2NtKUPkg3BM',
    }))).toBe(false);
  });

  it('is FALSE for press coverage quoting Eric', () => {
    expect(isSelfAmplification(entry({
      blockquote_source: 'Eric Ries, quoted by David Gelles in The New York Times',
      source_url: 'https://www.nytimes.com/2026/07/25/business/grady-white-boats.html',
    }))).toBe(false);
  });

  it('is FALSE for a third party posting on their own LinkedIn', () => {
    expect(isSelfAmplification(entry({
      blockquote_source: 'Lenny Rachitsky on LinkedIn',
      source_url: 'https://www.linkedin.com/posts/lennyrachitsky_each-month-activity-75',
    }))).toBe(false);
  });

  it('is FALSE for a reader endorsement hosted on incorruptible.co', () => {
    // Eric's venue, but the words are someone else's — still third-party praise.
    expect(isSelfAmplification(entry({
      blockquote_source: 'Leah Solivan',
      source_url: 'https://incorruptible.co',
    }))).toBe(false);
  });

  it('is FALSE when Eric is quoted inside someone else\'s event writeup', () => {
    expect(isSelfAmplification(entry({
      blockquote_source: 'Eric Ries at the Prosper breakfast (via Hattie Moll)',
      source_url: 'https://www.linkedin.com/posts/hattie-moll-78352616_early-morning',
    }))).toBe(false);
  });
});
