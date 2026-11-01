#!/usr/bin/env tsx
/**
 * What the sidebar job needs to know, derived rather than remembered.
 *
 *     npx tsx scripts/sidebar-state.ts
 *
 * The What's New rail used to be described to this job in prose, in its own
 * cron prompt: the current eight, the queued candidates, and the stated reason
 * each had been passed over. I rewrote that paragraph by hand every night.
 *
 * Prose cannot be re-derived, so it goes stale in two directions. A reason that
 * had stopped binding kept being applied — The Fourth Effect sat off the rail
 * for seven days on "it would take media to three", an objection a
 * media-for-media swap dissolved the moment it was recomputed. And a claim in
 * the same paragraph ("SOSV is the last event") was simply wrong once Corporate
 * Rebels announced a November date.
 *
 * Every bit of it was in the repo already: the rail is the entry files, its
 * history is git. See
 * docs/postmortems/2026-10-31-the-sidebar-remembered-in-prose.md
 *
 * This imports isSelfAmplification from the site's own lib rather than
 * reimplementing it. A second copy of a rule in a second language is the exact
 * failure this repo spent the same evening fixing in the quote gates.
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { isSelfAmplification } from '../src/lib/entries';

/** index.astro renders `.slice(0, 8)`. A ninth flag is dropped in silence. */
export const RAIL_SIZE = 8;

/** Types that have ever been featured; a reaction or review is not a candidate. */
export const STANDALONE = new Set(['endorsement', 'event', 'podcast', 'media', 'milestone']);

export interface EntryLike {
  id: string;
  date: string;
  type: string;
  blockquote_source?: string | null;
  source_url?: string | null;
  type_metadata?: Record<string, unknown> | null;
}

export function isFeatured(e: EntryLike): boolean {
  return Boolean(e.type_metadata?.featured);
}

export function composition(rail: EntryLike[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of rail) out[e.type] = (out[e.type] ?? 0) + 1;
  return out;
}

export interface RailChange {
  date: string;
  added: string[];
}

export interface Candidate {
  id: string;
  /** The day it became available to the rail. */
  available: string;
}

/**
 * How many rail changes happened after a candidate became available without
 * choosing it.
 *
 * This is deliberately "changes", not "cycles": the job runs nightly and a
 * quiet night is a legitimate no-change outcome, but git records only changes.
 * Counting what is actually recorded keeps the number honest — the prompt's
 * hand-kept prose had The Fourth Effect at "THREE consecutive pass-overs" when
 * the recorded figure was two.
 */
export function passOverCounts(
  candidates: Candidate[],
  changes: RailChange[]
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of candidates) {
    out[c.id] = changes.filter(
      (ch) => ch.date >= c.available && !ch.added.includes(c.id)
    ).length;
  }
  return out;
}

/**
 * Candidates that have already held a rail slot and been rotated out. They were
 * not passed over; they had their turn. Leaving them in buries the genuine case
 * under a list of normal retirements.
 */
export function excludeRetired(candidates: Candidate[], everFeatured: Set<string>): Candidate[] {
  return candidates.filter((c) => !everFeatured.has(c.id));
}

/**
 * Ways the flagged set and the rendered rail can disagree. Each one renders as
 * a silently short rail, because index.astro filters and then slices.
 */
export function railInvariantProblems(entries: EntryLike[]): string[] {
  const flagged = entries.filter(isFeatured);
  const problems: string[] = [];

  if (flagged.length !== RAIL_SIZE) {
    problems.push(
      `${flagged.length} entries carry type_metadata.featured, expected ${RAIL_SIZE}` +
        (flagged.length > RAIL_SIZE
          ? ` — index.astro slices to ${RAIL_SIZE}, so the extra is dropped without a word`
          : ' — the rail renders short')
    );
  }
  for (const e of flagged) {
    if (isSelfAmplification(e as never)) {
      problems.push(`${e.id} is flagged but the site filters it as self-amplification`);
    }
    if (e.type === 'reaction') {
      problems.push(`${e.id} is a reaction; the flag belongs on its parent`);
    }
    if (!STANDALONE.has(e.type) && e.type !== 'reaction') {
      problems.push(`${e.id} is type=${e.type}, which has never been featured`);
    }
  }
  return problems;
}

// ---------------------------------------------------------------- CLI

const ENTRIES = resolve(import.meta.dirname, '..', 'content', 'entries');

function loadAll(): EntryLike[] {
  return readdirSync(ENTRIES)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(readFileSync(resolve(ENTRIES, f), 'utf8')) as EntryLike);
}

function git(...args: string[]): string {
  return execFileSync('git', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
}

/** Rail membership at each commit that touched an entry, reduced to changes. */
function railHistory(since: string): { changes: RailChange[]; everFeatured: Set<string> } {
  const log = git(
    'log', `--since=${since}`, '--format=%H|%ad', '--date=format:%Y-%m-%d',
    '--', 'content/entries/'
  ).trim();
  if (!log) return { changes: [], everFeatured: new Set() };
  const commits = log.split('\n').map((l) => l.split('|')).reverse();

  const changes: RailChange[] = [];
  const everFeatured = new Set<string>();
  let prev: Set<string> | null = null;
  for (const [sha, date] of commits) {
    let ids: Set<string>;
    try {
      const out = git('grep', '-l', '"featured": true', sha, '--', 'content/entries/');
      ids = new Set(
        out.split(/\s+/).filter(Boolean)
          .map((p) => p.split('/').pop()!.replace(/\.json$/, ''))
      );
    } catch {
      continue; // grep exits non-zero when nothing matches
    }
    for (const id of ids) everFeatured.add(id);
    if (prev) {
      const added = [...ids].filter((i) => !prev!.has(i));
      const removed = [...prev].filter((i) => !ids.has(i));
      if (added.length || removed.length) changes.push({ date, added });
    }
    prev = ids;
  }
  return { changes, everFeatured };
}

function main(): void {
  const since = process.argv[2] ?? '2026-10-01';
  const entries = loadAll();
  const rail = entries.filter(isFeatured).sort((a, b) => b.date.localeCompare(a.date));

  console.log(`RAIL — ${rail.length} flagged\n`);
  for (const e of rail) console.log(`  ${e.date}  ${e.type.padEnd(11)} ${e.id}`);

  const comp = composition(rail);
  console.log(
    '\nCOMPOSITION  ' +
      Object.entries(comp).sort().map(([k, v]) => `${k} ${v}`).join(' · ')
  );

  const problems = railInvariantProblems(entries);
  console.log(problems.length ? '\nINVARIANT ✗' : '\nINVARIANT ✓  flags match what the site will render');
  for (const p of problems) console.log(`  ! ${p}`);

  const { changes, everFeatured } = railHistory(since);
  console.log(`\nRAIL CHANGES since ${since} (from git, oldest first)`);
  for (const c of changes) console.log(`  ${c.date}  + ${c.added.join(', ') || '(removal only)'}`);

  const today = new Date().toISOString().slice(0, 10);
  const candidates: Candidate[] = entries
    .filter((e) => !isFeatured(e) && STANDALONE.has(e.type))
    .filter((e) => !isSelfAmplification(e as never))
    .filter((e) => e.date >= since)
    // A future-dated event was available from the day it shipped, not its date.
    .map((e) => ({ id: e.id, available: e.date > today ? since : e.date }));

  const live = excludeRetired(candidates, everFeatured);
  const counts = passOverCounts(live, changes);
  const ranked = live
    .filter((c) => counts[c.id] > 0)
    .sort((a, b) => counts[b.id] - counts[a.id] || a.available.localeCompare(b.available));

  console.log('\nPASSED OVER — un-featured standalone candidates, by recorded rail changes since available');
  for (const c of ranked.slice(0, 12)) {
    const e = entries.find((x) => x.id === c.id)!;
    console.log(`  ${String(counts[c.id]).padStart(2)}×  ${e.type.padEnd(11)} ${c.id}`);
  }
  console.log(
    '\nA count is changes recorded in git, not nights the job ran; a quiet night\n' +
      'is a legitimate no-change outcome. High counts are a prompt to re-derive the\n' +
      'reason, not a reason to promote.'
  );
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop()!)) main();
