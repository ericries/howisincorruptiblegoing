import { describe, it, expect } from 'vitest';
import { buildRssFeed } from '../src/lib/rss';
import type { TimelineEntry } from '../src/lib/schema';

const entryFixture = (overrides: Partial<TimelineEntry> = {}): TimelineEntry => ({
  id: '2026-04-15-sample',
  date: '2026-04-15',
  type: 'review',
  title: 'Sample Title',
  summary: 'Sample summary.',
  blockquote: 'Sample quote.',
  blockquote_source: 'Sample Source',
  source_url: 'https://example.com/post',
  source_urls: null,
  video_url: null,
  image: null,
  attribution: null,
  attribution_title: null,
  attribution_image: null,
  tags: ['review'],
  type_metadata: {},
  scanner_source: 'manual',
  verified: true,
  created_at: '2026-04-15T00:00:00Z',
  ...overrides,
});

describe('buildRssFeed', () => {
  const SITE = 'https://howisincorruptiblegoing.com';

  it('emits a valid RSS 2.0 channel wrapper', () => {
    const xml = buildRssFeed([], SITE);
    expect(xml).toMatch(/^<\?xml version="1\.0" encoding="UTF-8"\?>/);
    expect(xml).toContain('<rss version="2.0"');
    expect(xml).toContain('<channel>');
    expect(xml).toContain('</channel>');
    expect(xml).toContain('</rss>');
    expect(xml).toContain(`<link>${SITE}/</link>`);
  });

  it('renders one <item> per entry', () => {
    const entries = [
      entryFixture({ id: 'a', date: '2026-04-10' }),
      entryFixture({ id: 'b', date: '2026-04-12' }),
      entryFixture({ id: 'c', date: '2026-04-15' }),
    ];
    const xml = buildRssFeed(entries, SITE);
    const itemCount = (xml.match(/<item>/g) ?? []).length;
    expect(itemCount).toBe(3);
  });

  it('sorts items newest first regardless of input order', () => {
    const entries = [
      entryFixture({ id: 'older', date: '2026-04-10', title: 'Older' }),
      entryFixture({ id: 'newer', date: '2026-04-15', title: 'Newer' }),
    ];
    const xml = buildRssFeed(entries, SITE);
    expect(xml.indexOf('Newer')).toBeLessThan(xml.indexOf('Older'));
  });

  it('escapes XML special characters in title, summary, and source', () => {
    const xml = buildRssFeed([
      entryFixture({
        title: 'AT&T <script> "test" \'escape\'',
        summary: 'Has & ampersands & <tags>',
      }),
    ], SITE);
    expect(xml).not.toMatch(/<script>/);
    expect(xml).toContain('AT&amp;T');
    expect(xml).toContain('&lt;script&gt;');
    expect(xml).toContain('&quot;test&quot;');
    expect(xml).toContain('Has &amp; ampersands');
  });

  it('uses entry.id as guid with isPermaLink="false"', () => {
    const xml = buildRssFeed([entryFixture({ id: '2026-04-15-sample' })], SITE);
    expect(xml).toContain('<guid isPermaLink="false">2026-04-15-sample</guid>');
  });

  it('formats pubDate as RFC 822', () => {
    const xml = buildRssFeed([entryFixture({ date: '2026-04-15' })], SITE);
    // RFC 822 format: "Wed, 15 Apr 2026 12:00:00 GMT"
    expect(xml).toMatch(/<pubDate>[A-Za-z]{3}, \d{2} [A-Za-z]{3} 2026 \d{2}:\d{2}:\d{2} GMT<\/pubDate>/);
  });

  it('builds item link as site URL with entry id anchor', () => {
    const xml = buildRssFeed([entryFixture({ id: '2026-04-15-sample' })], SITE);
    expect(xml).toContain(`<link>${SITE}/#2026-04-15-sample</link>`);
  });

  it('includes entry summary in description', () => {
    const xml = buildRssFeed([
      entryFixture({ summary: 'A specific summary string for this entry.' }),
    ], SITE);
    expect(xml).toContain('A specific summary string for this entry.');
  });
});
