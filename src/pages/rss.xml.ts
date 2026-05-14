import type { APIContext } from 'astro';
import * as path from 'path';
import { loadEntries } from '../lib/entries';
import { buildRssFeed } from '../lib/rss';

export async function GET({ site }: APIContext): Promise<Response> {
  const entriesDir = path.join(process.cwd(), 'content', 'entries');
  // Reactions cluster under their parent on the timeline and don't get their own RSS item.
  const entries = loadEntries(entriesDir).filter(e => e.type !== 'reaction');
  const siteUrl = site ? site.toString().replace(/\/$/, '') : 'https://howisincorruptiblegoing.com';
  const xml = buildRssFeed(entries, siteUrl);

  return new Response(xml, {
    status: 200,
    headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' },
  });
}
