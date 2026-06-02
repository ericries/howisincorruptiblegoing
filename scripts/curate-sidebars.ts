#!/usr/bin/env tsx
// One-shot sidebar curation: trim featured (16->8) and highlight (16->6)
// per memory/feedback_sidebar_flags.md, removing flags from entries that
// dropped out of the top N. Modifies type_metadata in place — deletes the
// key entirely rather than setting it to false/empty.

import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ENTRIES = resolve(import.meta.dirname, '..', 'content/entries');

const REMOVE_FEATURED = [
  '2026-05-26-bob-sutton-launch-day-blurb',
  '2026-05-26-porchlight-qa-incorruptible',
  '2026-05-26-reader-lisa-brennan-jobs',
  '2026-05-26-rob-walling-startups-for-the-rest-of-us',
  '2026-05-26-thought-sparks-rita-mcgrath',
  '2026-05-28-penguin-life-publisher-blurbs',
  '2026-05-29-matt-blumberg-book-short-review',
  '2026-05-29-seedcamp-carlos-espinal',
];

const REMOVE_HIGHLIGHT = [
  '2026-01-08-reader-jessica-jackley',
  '2026-02-27-endorsement-tim-oreilly',
  '2026-03-19-endorsement-matt-blumberg',
  '2026-04-01-endorsement-ken-chenault',
  '2026-04-08-endorsement-daniel-pink',
  '2026-04-16-kim-scott-radical-candor-podcast',
  '2026-05-16-frances-frei-incorruptible-comment',
  '2026-05-26-bob-sutton-launch-day-blurb',
  '2026-05-26-nir-eyal-launch-day-tweet',
  '2026-05-27-karri-saarinen-linear-tweet',
];

function patch(id: string, op: (meta: Record<string, unknown>) => boolean) {
  const p = resolve(ENTRIES, `${id}.json`);
  const e = JSON.parse(readFileSync(p, 'utf8'));
  e.type_metadata = e.type_metadata || {};
  const changed = op(e.type_metadata);
  if (changed) {
    writeFileSync(p, JSON.stringify(e, null, 2) + '\n');
    console.log('UPDATED', id);
  } else {
    console.log('NOOP   ', id);
  }
}

for (const id of REMOVE_FEATURED) {
  patch(id, (m) => {
    if (m.featured === undefined) return false;
    delete m.featured;
    return true;
  });
}
for (const id of REMOVE_HIGHLIGHT) {
  patch(id, (m) => {
    if (m.highlight === undefined) return false;
    delete m.highlight;
    return true;
  });
}
console.log('Done.');
