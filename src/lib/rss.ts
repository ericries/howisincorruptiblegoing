import type { TimelineEntry } from './schema';

function escapeXml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function toRfc822(date: string): string {
  // Entry dates are YYYY-MM-DD; use noon UTC so the date renders as
  // expected across all timezones without crossing day boundaries.
  return new Date(`${date}T12:00:00Z`).toUTCString();
}

export function buildRssFeed(entries: TimelineEntry[], siteUrl: string): string {
  const sorted = [...entries].sort((a, b) => b.date.localeCompare(a.date));
  const lastBuild = new Date().toUTCString();

  const items = sorted
    .map((e) => {
      const link = `${siteUrl}/#${e.id}`;
      return `    <item>
      <title>${escapeXml(e.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="false">${escapeXml(e.id)}</guid>
      <pubDate>${toRfc822(e.date)}</pubDate>
      <description>${escapeXml(e.summary)}</description>
    </item>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>How Is Incorruptible Going?</title>
    <link>${siteUrl}/</link>
    <atom:link href="${siteUrl}/rss.xml" rel="self" type="application/rss+xml" />
    <description>Timeline tracking momentum for Eric Ries's book Incorruptible (May 26, 2026).</description>
    <language>en-us</language>
    <lastBuildDate>${lastBuild}</lastBuildDate>
${items}
  </channel>
</rss>`;
}
