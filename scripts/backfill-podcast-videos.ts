#!/usr/bin/env tsx
// One-shot backfill: for podcast entries that have a YouTube version we
// just discovered, set entry.video_url to the YouTube URL so the Now
// Playing strip switches from letterboxed iTunes art to the episode-
// specific ytimg thumbnail.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const ENTRIES_DIR = resolve(ROOT, 'content/entries');

const TARGETS: Record<string, string> = {
  '2026-04-21-anthony-taylor-strategy-podcast': 'https://www.youtube.com/watch?v=V6QQLmna03M',
  '2026-05-26-inverted-podcast-become-incorruptible': 'https://www.youtube.com/watch?v=VKJBtSKGwj8',
  '2026-05-26-leading-learning-jeff-cobb': 'https://www.youtube.com/watch?v=GG4KEsxz1aQ',
  '2026-05-26-keen-on-beyond-lean-startup': 'https://www.youtube.com/watch?v=Z8K8He7fbDo',
  '2026-05-26-startup-leap-founder-lost-control': 'https://www.youtube.com/watch?v=B4OVMaoZ1os',
  '2026-05-25-startup-podcast-yaniv-bernstein': 'https://www.youtube.com/watch?v=HQ7cP1lGyiM',
  '2026-05-26-thought-sparks-rita-mcgrath': 'https://www.youtube.com/watch?v=ux9KQRBvVAE',
  '2026-05-28-fomo-sapiens-patrick-mcginnis': 'https://www.youtube.com/watch?v=J3Vm2_Tauu8',
  '2026-05-28-innovation-show-aidan-mccullen': 'https://www.youtube.com/watch?v=JDjzR2nuctA',
  '2026-05-26-rapid-response-bob-safian': 'https://www.youtube.com/watch?v=yAj1FrM1pTA',
  '2026-05-26-rob-walling-startups-for-the-rest-of-us': 'https://www.youtube.com/watch?v=R0dhsHrxsQo',
  '2026-05-28-breaking-precedent-leah-solivan': 'https://www.youtube.com/watch?v=Cvu-lRcJYzU',
  '2026-05-26-tech-lead-journal-259-suryawirawan': 'https://www.youtube.com/watch?v=jF8J3CmPdi4',
  '2026-05-26-bubble-new-build-straschnov': 'https://www.youtube.com/watch?v=YKYUT3QENw8',
  '2026-06-01-brave-southeast-asia-e700-jeremy-au': 'https://www.youtube.com/watch?v=8wihh7uYpRo',
  '2026-05-25-coaching-for-leaders-dave-stachowiak': 'https://www.youtube.com/watch?v=fHNyYk7OB3o',
  '2026-06-01-how-of-business-609-henry-lopez': 'https://www.youtube.com/watch?v=FfV71RRBVcE',
  '2026-05-18-ryan-honeyman-b-corp-podcast': 'https://www.youtube.com/watch?v=wQDtkDPS62A',
  '2026-05-29-commit-and-push-damien-filiatrault': 'https://www.youtube.com/watch?v=77oboRQi4mE',
  '2026-05-27-ignite-podcast-brian-bell': 'https://www.youtube.com/watch?v=F4LMg9hi_EI',
  '2026-05-26-tbpn-launch-day-clips': 'https://www.youtube.com/watch?v=AWuE2Ru2SrE',
  '2026-05-26-inside-outside-brian-ardinger': 'https://www.youtube.com/watch?v=h_89JOBm0-k',
  '2026-05-26-product-podcast-villaumbrosia': 'https://www.youtube.com/watch?v=Z_kt59g2Rk8',
  '2026-04-16-humans-in-the-loop-podcast': 'https://www.youtube.com/watch?v=Dve3DaaCDgI',
  '2026-05-25-info-tech-digital-disruption-podcast': 'https://www.youtube.com/watch?v=-ggxydGbG_Y',
};

let updated = 0;
let missing = 0;
let already = 0;
for (const [id, ytUrl] of Object.entries(TARGETS)) {
  const p = resolve(ENTRIES_DIR, `${id}.json`);
  if (!existsSync(p)) {
    console.log(`MISS ${id} — file not found`);
    missing++;
    continue;
  }
  const entry = JSON.parse(readFileSync(p, 'utf8'));
  if (entry.video_url === ytUrl) {
    already++;
    continue;
  }
  entry.video_url = ytUrl;
  writeFileSync(p, JSON.stringify(entry, null, 2) + '\n');
  updated++;
  console.log(`SET  ${id}`);
}
console.log(`\n${updated} updated, ${already} already set, ${missing} missing.`);
