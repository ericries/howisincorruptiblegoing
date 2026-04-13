import * as fs from 'fs';
import * as path from 'path';

/**
 * Verify that each entry's blockquote text actually appears
 * at the source_url. Reports mismatches so we can fix them.
 *
 * Usage: npx tsx scripts/verify-quotes.ts
 */

const entriesDir = path.join(process.cwd(), 'content', 'entries');

interface Entry {
  id: string;
  blockquote: string;
  blockquote_source: string;
  source_url: string;
  source_urls?: { url: string; label: string }[] | null;
  type: string;
  attribution?: string | null;
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\u2018\u2019\u201C\u201D]/g, "'")  // smart quotes → straight
    .replace(/\u2014/g, '--')                       // em dash
    .replace(/\u2013/g, '-')                        // en dash
    .replace(/\u2026/g, '...')                      // ellipsis
    .replace(/\s+/g, ' ')                           // collapse whitespace
    .trim();
}

// Check if quote appears in page content. We check substrings
// of increasing length to find partial matches too.
function findQuoteInPage(quote: string, pageText: string): { found: boolean; partial: boolean; matchedChars: number } {
  const nq = normalize(quote);
  const np = normalize(pageText);

  if (np.includes(nq)) {
    return { found: true, partial: false, matchedChars: nq.length };
  }

  // Try first 60 chars as a partial match
  const shortQuote = nq.slice(0, 60);
  if (np.includes(shortQuote)) {
    return { found: false, partial: true, matchedChars: 60 };
  }

  // Try first 30 chars
  const veryShort = nq.slice(0, 30);
  if (np.includes(veryShort)) {
    return { found: false, partial: true, matchedChars: 30 };
  }

  return { found: false, partial: false, matchedChars: 0 };
}

async function fetchPage(url: string): Promise<{ ok: boolean; text: string; status: number }> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const resp = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; IncorruptibleBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml',
      },
      redirect: 'follow',
    });
    clearTimeout(timeout);
    const text = await resp.text();
    return { ok: resp.ok, text, status: resp.status };
  } catch (e) {
    return { ok: false, text: '', status: 0 };
  }
}

async function main() {
  const files = fs.readdirSync(entriesDir).filter(f => f.endsWith('.json'));
  let errors = 0;
  let warnings = 0;
  let passes = 0;
  let skips = 0;

  for (const file of files.sort()) {
    const entry: Entry = JSON.parse(fs.readFileSync(path.join(entriesDir, file), 'utf-8'));

    // Skip endorsements that link to incorruptible.co — blurbs won't be on the homepage
    if (entry.type === 'endorsement' && entry.source_url === 'https://incorruptible.co') {
      console.log(`⏭  ${file} — endorsement blurb (skip, not on homepage)`);
      skips++;
      continue;
    }

    // Skip LinkedIn URLs — they require auth
    if (entry.source_url.includes('linkedin.com')) {
      console.log(`⏭  ${file} — LinkedIn (requires auth, skip)`);
      skips++;
      continue;
    }

    // Skip Twitter/X — requires auth
    if (entry.source_url.includes('x.com') || entry.source_url.includes('twitter.com')) {
      console.log(`⏭  ${file} — Twitter/X (requires auth, skip)`);
      skips++;
      continue;
    }

    // Fetch the page
    const page = await fetchPage(entry.source_url);

    if (!page.ok) {
      console.log(`⚠️  ${file} — could not fetch ${entry.source_url} (status ${page.status})`);
      warnings++;
      continue;
    }

    // Check quote
    const result = findQuoteInPage(entry.blockquote, page.text);

    if (result.found) {
      console.log(`✅ ${file} — quote verified`);
      passes++;
    } else if (result.partial) {
      console.log(`⚠️  ${file} — PARTIAL match (first ${result.matchedChars} chars)`);
      console.log(`   Quote: "${entry.blockquote.slice(0, 80)}..."`);
      console.log(`   URL: ${entry.source_url}`);
      warnings++;
    } else {
      console.log(`❌ ${file} — QUOTE NOT FOUND on page`);
      console.log(`   Quote: "${entry.blockquote.slice(0, 100)}..."`);
      console.log(`   URL: ${entry.source_url}`);
      errors++;
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`Results: ${passes} pass, ${warnings} warn, ${errors} FAIL, ${skips} skip`);
  console.log(`${'='.repeat(60)}`);

  process.exit(errors > 0 ? 1 : 0);
}

main();
