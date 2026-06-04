#!/usr/bin/env tsx
// One-shot sidebar curation: trim featured (11->8) per
// memory/feedback_sidebar_flags.md. Highlights already at 6 — no change.

import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ENTRIES = resolve(import.meta.dirname, '..', 'content/entries');

const REMOVE_FEATURED = [
  '2026-05-30-jennifer-pahlka-incorruptible-interview',
  '2026-06-01-raphaelle-kennedy-book-of-the-year',
  '2026-06-01-ryan-martens-rally-software-review',
];

const REMOVE_HIGHLIGHT: string[] = [];

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
