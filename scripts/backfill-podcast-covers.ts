#!/usr/bin/env tsx
// One-shot backfill: for each podcast entry missing an image, look up the show
// on iTunes Search API and download artworkUrl600 to /images/podcasts/<slug>.jpg,
// then patch the entry JSON. Skips entries whose iTunes lookup returns no
// match — those stay imageless (won't show in the strip).

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const ENTRIES_DIR = resolve(ROOT, 'content/entries');
const COVERS_DIR = resolve(ROOT, 'public/images/podcasts');

// Entry id -> { itunes search term, target slug (filename without .jpg) }.
// Search term tuned per show so iTunes returns the right podcast in the
// top result. Slugs match the existing /images/podcasts/ naming convention.
const TARGETS: Record<string, { search: string; slug: string }> = {
  '2026-03-31-acgc-podcast': { search: 'ACG GrowthTV', slug: 'acgc-podcast' },
  '2026-03-31-boardroom-governance-podcast': { search: 'Boardroom Governance Evan Epstein', slug: 'boardroom-governance' },
  '2026-04-01-new-books-network': { search: 'New Books in Business and Economics', slug: 'new-books-network' },
  '2026-04-16-humans-in-the-loop-podcast': { search: 'Humans in the Loop Seb Agertoft', slug: 'humans-in-the-loop' },
  '2026-04-20-pcdn-social-change-podcast': { search: 'Social Change Career Craig Zelizer', slug: 'pcdn-social-change-career' },
  '2026-04-21-anthony-taylor-strategy-podcast': { search: 'SME Strategy Anthony Taylor', slug: 'sme-strategy' },
  '2026-04-22-corporate-venturing-podcast-ritorto': { search: 'The Corporate Venturing Podcast Davide Ritorto', slug: 'corporate-venturing-podcast' },
  '2026-05-12-rachel-botsman-rethinking-trust': { search: 'Rethinking Trust Rachel Botsman', slug: 'rethinking-trust' },
  '2026-05-18-ryan-honeyman-b-corp-podcast': { search: 'B Corp Podcast Ryan Honeyman', slug: 'b-corp-podcast' },
  '2026-05-20-kara-goldin-show-podcast': { search: 'The Kara Goldin Show', slug: 'kara-goldin-show' },
  '2026-05-25-before-the-bestseller-alex-strathdee': { search: 'Before the Bestseller Alex Strathdee', slug: 'before-the-bestseller' },
  '2026-05-25-coaching-for-leaders-dave-stachowiak': { search: 'Coaching for Leaders Dave Stachowiak', slug: 'coaching-for-leaders' },
  '2026-05-25-info-tech-digital-disruption-podcast': { search: 'Digital Disruption Geoff Nielson', slug: 'digital-disruption' },
  '2026-05-25-startup-podcast-yaniv-bernstein': { search: 'The Startup Podcast Yaniv Bernstein', slug: 'the-startup-podcast' },
  '2026-05-26-bcg-henderson-thinkers-ideas-adam-job': { search: 'BCG Henderson Institute Thinkers and Ideas', slug: 'bcg-henderson-thinkers-ideas' },
  '2026-05-26-keen-on-beyond-lean-startup': { search: 'Keen On America Andrew Keen', slug: 'keen-on' },
  '2026-05-26-product-podcast-villaumbrosia': { search: 'The Product Podcast Product School', slug: 'the-product-podcast' },
  '2026-05-26-rapid-response-bob-safian': { search: 'Rapid Response Bob Safian', slug: 'rapid-response' },
  '2026-05-26-rob-walling-startups-for-the-rest-of-us': { search: 'Startups For the Rest of Us Rob Walling', slug: 'startups-for-the-rest-of-us' },
  '2026-05-26-thought-sparks-rita-mcgrath': { search: 'Thought Sparks Rita McGrath', slug: 'thought-sparks' },
  '2026-05-28-netguru-next-in-commerce': { search: 'Disruption Talks Netguru', slug: 'disruption-talks-netguru' },
  '2026-05-29-career-sessions-james-lowry': { search: 'Career Sessions Career Lessons James Lowry', slug: 'career-sessions-career-lessons' },
  '2026-05-29-commit-and-push-damien-filiatrault': { search: 'Commit and Push Damien Filiatrault Scopic', slug: 'commit-and-push' },
  '2026-05-29-corporate-venturing-podcast-davide-ritorto': { search: 'The Corporate Venturing Podcast Davide Ritorto', slug: 'corporate-venturing-podcast' },
  '2026-05-29-do-good-to-lead-well-craig-dowden': { search: 'Do Good to Lead Well Craig Dowden', slug: 'do-good-to-lead-well' },
  '2026-05-29-pcdn-social-change-career-craig-zelizer': { search: 'Social Change Career Craig Zelizer', slug: 'pcdn-social-change-career' },
  '2026-05-29-seedcamp-carlos-espinal': { search: 'Seedcamp Podcast', slug: 'seedcamp' },
  '2026-06-26-cxotalk-michael-krigsman': { search: 'CXOTalk Michael Krigsman', slug: 'cxotalk' },
};

interface ItunesHit {
  artworkUrl600?: string;
  collectionName?: string;
  trackName?: string;
}

async function lookupArtwork(search: string): Promise<string | null> {
  const url = `https://itunes.apple.com/search?term=${encodeURIComponent(search)}&entity=podcast&limit=1`;
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = (await res.json()) as { results?: ItunesHit[] };
  const hit = data.results?.[0];
  if (!hit?.artworkUrl600) return null;
  return hit.artworkUrl600;
}

async function downloadTo(url: string, target: string): Promise<boolean> {
  const res = await fetch(url);
  if (!res.ok) return false;
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(target, buf);
  return true;
}

async function main() {
  let imagedCount = 0;
  let downloadCount = 0;
  let skipped: string[] = [];

  for (const [entryId, { search, slug }] of Object.entries(TARGETS)) {
    const entryPath = resolve(ENTRIES_DIR, `${entryId}.json`);
    if (!existsSync(entryPath)) {
      console.log(`SKIP ${entryId} — entry file missing`);
      skipped.push(entryId);
      continue;
    }
    const coverPath = resolve(COVERS_DIR, `${slug}.jpg`);
    const imageWebPath = `/images/podcasts/${slug}.jpg`;

    // Download cover if not already cached locally.
    if (!existsSync(coverPath)) {
      const artworkUrl = await lookupArtwork(search);
      if (!artworkUrl) {
        console.log(`SKIP ${entryId} — iTunes returned no match for "${search}"`);
        skipped.push(entryId);
        continue;
      }
      const ok = await downloadTo(artworkUrl, coverPath);
      if (!ok) {
        console.log(`SKIP ${entryId} — failed to download ${artworkUrl}`);
        skipped.push(entryId);
        continue;
      }
      downloadCount++;
      console.log(`DL   ${slug}.jpg`);
    }

    // Patch the entry to point at the cover.
    const entry = JSON.parse(readFileSync(entryPath, 'utf8'));
    if (entry.image === imageWebPath) continue;
    entry.image = imageWebPath;
    writeFileSync(entryPath, JSON.stringify(entry, null, 2) + '\n');
    imagedCount++;
    console.log(`SET  ${entryId} -> ${imageWebPath}`);
  }

  console.log(`\nDone. ${downloadCount} covers downloaded, ${imagedCount} entries patched, ${skipped.length} skipped.`);
  if (skipped.length) console.log('Skipped:', skipped);
}

main();
