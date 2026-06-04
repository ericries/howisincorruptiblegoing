#!/usr/bin/env tsx
// One-shot: restore the 10 highlight flags incorrectly pruned in commit
// e035e0d ("sidebar curation: trim Featured to 8 and Highlights to 6").
// The Highlights row is meant to GROW over time, not be capped — see
// memory/feedback_highlights_row_grows.md.

import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ENTRIES = resolve(import.meta.dirname, '..', 'content/entries');

interface Restore {
  id: string;
  add: Record<string, unknown>;
}

const RESTORES: Restore[] = [
  { id: '2026-01-08-reader-jessica-jackley', add: { highlight: "Jessica Jackley: 'This book nearly brought me to tears.'" } },
  { id: '2026-02-27-endorsement-tim-oreilly', add: { highlight: "Tim O'Reilly: 'If you want the world to be a better place than it is, this book is a good place to start.'", face_position: 'center 15%' } },
  { id: '2026-03-19-endorsement-matt-blumberg', add: { highlight: "Matt Blumberg: 'this book will help you walk out with your soul intact'" } },
  { id: '2026-04-01-endorsement-ken-chenault', add: { highlight: "Ken Chenault: 'Incorruptible demonstrates the importance of mission-driven leadership and defying the status quo'" } },
  { id: '2026-04-08-endorsement-daniel-pink', add: { highlight: "Daniel Pink: 'a bracingly practical vision of how companies can stay true and still win'", face_position: 'center 75%' } },
  { id: '2026-04-16-kim-scott-radical-candor-podcast', add: { highlight: "Kim Scott: 'One of the most important books I've read in the last decade'", sidebar_quote: "It's one of the most important books I've read in the last decade. Companies don't fail their missions because of bad people. They fail because of bad structures.", hero_quote_label: "most important books I've read in the last decade", hero_quote_author: 'Kim Scott' } },
  { id: '2026-05-16-frances-frei-incorruptible-comment', add: { highlight: "Frances Frei: 'I was LOUD. Shouting, loud.'" } },
  { id: '2026-05-26-bob-sutton-launch-day-blurb', add: { highlight: "Bob Sutton: 'a rare joy to read'", sidebar_quote: 'Incorruptible destroys the myth that only sleazy founders and companies get rich. Eric Ries shows you how to build a mission-driven company that will be humane, ethical, and make piles of money for decades.' } },
  { id: '2026-05-26-nir-eyal-launch-day-tweet', add: { highlight: "Nir Eyal: 'institutions that endure without losing their soul'", sidebar_quote: 'A thoughtful, timely, and important read for founders, leaders, and anyone trying to build institutions that endure without losing their soul.' } },
  { id: '2026-05-27-karri-saarinen-linear-tweet', add: { highlight: "Karri Saarinen: 'eye-opening how many great, purpose-driven companies eventually get corrupted'" } },
];

for (const { id, add } of RESTORES) {
  const p = resolve(ENTRIES, `${id}.json`);
  const e = JSON.parse(readFileSync(p, 'utf8'));
  e.type_metadata = e.type_metadata || {};
  let changed = false;
  for (const [k, v] of Object.entries(add)) {
    if (e.type_metadata[k] !== v) {
      e.type_metadata[k] = v;
      changed = true;
    }
  }
  if (changed) {
    writeFileSync(p, JSON.stringify(e, null, 2) + '\n');
    console.log('RESTORED', id);
  } else {
    console.log('NOOP    ', id);
  }
}
console.log('Done.');
