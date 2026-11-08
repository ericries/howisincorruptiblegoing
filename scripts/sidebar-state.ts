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
/**
 * The day a candidate became available to the rail.
 *
 * This decided the pass-over counts, and a future-dated entry used to be given
 * the START OF THE WINDOW — so an entry that shipped this morning was reported
 * as passed over by every change since. On 2026-11-01 the Spanish edition,
 * committed that day, topped the list at 20x, which is exactly the number of
 * recorded changes and therefore the maximum the report can produce. The
 * report's strongest signal was manufactured, and it pointed at the newest
 * entries instead of the longest-waiting ones.
 *
 * The honest answer is the day the entry shipped — an entry cannot be passed
 * over before it exists. That also fixes the quieter case in the other
 * direction: Kass Lazerow is dated 10-07 and was committed on the 9th, so two
 * changes were being counted against an entry nobody could have chosen.
 */
export function availableFrom(
  entry: { id: string; date: string; shipped?: string },
  since: string,
  today: string
): string {
  if (entry.shipped) return entry.shipped > entry.date ? entry.shipped : entry.date;
  return entry.date > today ? today : entry.date;
}

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
/**
 * The order the report prints candidates in: newest first, every one of them.
 *
 * It used to sort by pass-over count descending, drop anything at zero, and
 * slice to twelve — which hid the nine newest candidates on 2026-11-06,
 * Thinkers50 among them, on the night it was the right pick. Sorting by count
 * puts a fresh entry last by definition, and the prompt is explicit that the
 * count is a prompt to re-derive a reason, never a ranking. So the count is an
 * annotation here, not the sort key, and nothing is cut.
 */
/**
 * `null` when the candidate listing accounts for every standalone entry in the
 * window; otherwise the discrepancy, in words.
 *
 * Every standalone entry in the window is either on the rail, retired from it,
 * or a candidate — there is no fourth bucket. If the listing does not satisfy
 * that, rows were dropped on the way to the page, and nothing else about the
 * report would show it.
 */
/** The job curates "the past 30 days of content/entries/". */
export const CURATION_WINDOW_DAYS = 30;

/**
 * Whether an entry is still promotable by date.
 *
 * The candidate listing is built from `since` — the rail-HISTORY window, 1
 * October — which is a longer reach than the job's own 30-day curation scope.
 * So the list offers entries that may not be promoted, and because pass-over
 * counts only ever climb, the aged-out ones drift to the top of the count
 * column: on 2026-11-07 the two highest, 19x and 15x, were both simply too old.
 *
 * A future date is inside the window — a forward-looking slot has not aged out.
 */
export function isWithinCurationWindow(
  date: string,
  today: string,
  days: number = CURATION_WINDOW_DAYS
): boolean {
  const ms = Date.parse(`${today}T00:00:00Z`) - Date.parse(`${date}T00:00:00Z`);
  if (Number.isNaN(ms)) return true; // unparseable: do not hide it on a guess
  return ms / 86_400_000 <= days;
}

export function candidateReconciliation(n: {
  standalone: number;
  featured: number;
  retired: number;
  shown: number;
}): string | null {
  const expected = n.standalone - n.featured - n.retired;
  if (expected === n.shown) return null;
  const verb = n.shown < expected ? 'missing' : 'surplus';
  return (
    `candidate listing does not reconcile: ${n.standalone} standalone ` +
    `− ${n.featured} featured − ${n.retired} retired = ${expected}, ` +
    `but ${n.shown} shown (${Math.abs(expected - n.shown)} ${verb})`
  );
}

export function rankForReport(
  candidates: Candidate[],
  counts: Record<string, number>
): Candidate[] {
  void counts;
  return [...candidates].sort(
    (a, b) => b.available.localeCompare(a.available) || a.id.localeCompare(b.id)
  );
}

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

/** The day an entry file was first committed, or undefined if git cannot say. */
function shippedOn(id: string): string | undefined {
  try {
    const out = execSync(
      `git log --diff-filter=A --format=%ad --date=short -- content/entries/${id}.json`,
      { cwd: ROOT, encoding: 'utf-8' }
    ).trim().split('\n').filter(Boolean);
    return out.length ? out[out.length - 1] : undefined;
  } catch {
    return undefined;
  }
}

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
    .map((e) => ({
      id: e.id,
      available: availableFrom({ id: e.id, date: e.date, shipped: shippedOn(e.id) }, since, today),
    }));

  const live = excludeRetired(candidates, everFeatured);
  const counts = passOverCounts(live, changes);
  const ranked = rankForReport(live, counts);

  const standaloneInWindow = entries.filter(
    (e) => e.date >= since && STANDALONE.has(e.type) && !isSelfAmplification(e as never)
  ).length;
  const discrepancy = candidateReconciliation({
    standalone: standaloneInWindow,
    featured: entries.filter((e) => isFeatured(e) && e.date >= since).length,
    retired: candidates.length - live.length,
    shown: ranked.length,
  });
  if (discrepancy) {
    console.log(`\nCANDIDATE LISTING ✗  ${discrepancy}`);
    process.exitCode = 1;
  }

  console.log(
    `\nCANDIDATES — ${ranked.length} un-featured standalone entries, newest first.` +
      '\n(N× = recorded rail changes that have passed it over since it became available)'
  );
  let agedOut = 0;
  for (const c of ranked) {
    const e = entries.find((x) => x.id === c.id)!;
    const n = counts[c.id] ?? 0;
    const stale = !isWithinCurationWindow(e.date, today);
    if (stale) agedOut++;
    const mark = stale ? '  — outside the 30-day window, not promotable' : '';
    console.log(`  ${e.date}  ${String(n).padStart(2)}×  ${e.type.padEnd(11)} ${c.id}${mark}`);
  }
  if (agedOut) {
    console.log(
      `\n  ${agedOut} candidate(s) above have aged out of the 30-day curation window.` +
        '\n  Their pass-over counts keep climbing and mean nothing; they are listed,' +
        '\n  not hidden, so the reconciliation still balances.'
    );
  }
  console.log(
    '\nA count is changes recorded in git, not nights the job ran; a quiet night\n' +
      'is a legitimate no-change outcome. High counts are a prompt to re-derive the\n' +
      'reason, not a reason to promote.'
  );
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop()!)) main();
