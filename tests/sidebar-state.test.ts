import { describe, it, expect } from 'vitest';
import {
  availableFrom,
  composition,
  passOverCounts,
  railInvariantProblems,
  rankForReport,
  candidateReconciliation,
  RAIL_SIZE,
} from '../scripts/sidebar-state';

/**
 * The sidebar job's memory used to be a paragraph in its own cron prompt,
 * rewritten by hand each night: the current rail, the queued candidates, and
 * the reason each had been passed over. Prose cannot be re-derived, so a reason
 * that had stopped binding kept being re-applied — The Fourth Effect sat off
 * the rail for seven days on "it would take media to three", which a
 * media-for-media swap dissolved the moment anyone recomputed it.
 *
 * All of it was derivable from the repo the whole time: the rail from the
 * entry files, its history from git.
 *
 * See docs/postmortems/2026-10-31-the-sidebar-remembered-in-prose.md
 */

const ENTRY = (over: Record<string, unknown> = {}) => ({
  id: '2026-10-24-x', date: '2026-10-24', type: 'media',
  blockquote_source: 'Someone Else', source_url: 'https://example.com/a',
  type_metadata: {}, ...over,
});

describe('composition', () => {
  it('counts the rail by entry type', () => {
    const rail = [
      ENTRY({ id: 'a', type: 'event' }), ENTRY({ id: 'b', type: 'event' }),
      ENTRY({ id: 'c', type: 'media' }), ENTRY({ id: 'd', type: 'podcast' }),
    ];
    expect(composition(rail)).toEqual({ event: 2, media: 1, podcast: 1 });
  });

  it('is empty for an empty rail', () => {
    expect(composition([])).toEqual({});
  });
});

describe('passOverCounts', () => {
  // Rail changes, newest last. A candidate is passed over by every change that
  // happened after it became available and did not add it.
  const changes = [
    { date: '2026-10-28', added: ['giant-robots'] },
    { date: '2026-10-30', added: ['corporate-rebels'] },
  ];

  it('counts changes since the candidate became available', () => {
    const got = passOverCounts([{ id: 'fourth-effect', available: '2026-10-24' }], changes);
    expect(got['fourth-effect']).toBe(2);
  });

  it('does not count changes that predate availability', () => {
    const got = passOverCounts([{ id: 'late-arrival', available: '2026-10-29' }], changes);
    expect(got['late-arrival']).toBe(1);
  });

  it('does not count the change that added the candidate itself', () => {
    const got = passOverCounts([{ id: 'giant-robots', available: '2026-10-22' }], changes);
    expect(got['giant-robots']).toBe(1); // the 10-30 change only
  });

  it('is zero for a candidate newer than every change', () => {
    const got = passOverCounts([{ id: 'brand-new', available: '2026-10-31' }], changes);
    expect(got['brand-new']).toBe(0);
  });
});

describe('railInvariantProblems', () => {
  const ok = Array.from({ length: RAIL_SIZE }, (_, i) =>
    ENTRY({ id: `e${i}`, type_metadata: { featured: true } }));

  it('passes a well-formed rail', () => {
    expect(railInvariantProblems(ok)).toEqual([]);
  });

  it('catches a ninth flag, which index.astro would silently drop', () => {
    const nine = [...ok, ENTRY({ id: 'e8', type_metadata: { featured: true } })];
    const problems = railInvariantProblems(nine);
    expect(problems.join(' ')).toMatch(/9 entries carry/);
  });

  it('catches too few, which leaves a hole in the rail', () => {
    expect(railInvariantProblems(ok.slice(0, 7)).join(' ')).toMatch(/7 entries carry/);
  });

  it('catches a flagged entry the site filters out as self-amplification', () => {
    // Flagged, but sourced to Eric speaking on his own feed: index.astro drops
    // it, so the rail silently renders seven.
    const self = ENTRY({
      id: 'eric-own', blockquote_source: 'Eric Ries on LinkedIn',
      source_url: 'https://www.linkedin.com/posts/eries_something-activity-1234',
      type_metadata: { featured: true },
    });
    const rail = [...ok.slice(0, RAIL_SIZE - 1), self];
    expect(railInvariantProblems(rail).join(' ')).toMatch(/self-amplification/i);
  });

  it('catches a reaction carrying the flag', () => {
    const rail = [...ok.slice(0, RAIL_SIZE - 1),
                  ENTRY({ id: 'r', type: 'reaction', type_metadata: { featured: true } })];
    expect(railInvariantProblems(rail).join(' ')).toMatch(/reaction/i);
  });
});

/**
 * A candidate that already had its turn on the rail and was rotated out is not
 * being passed over. The first run of this report ranked Design Observer and
 * Stanford eCorner at the top of the "passed over" list; both had been featured
 * for days and retired normally. Counting a retirement as a snub buries the
 * genuine case — which is the one thing this report exists to surface.
 */
import { excludeRetired } from '../scripts/sidebar-state';

describe('excludeRetired', () => {
  const candidates = [
    { id: 'never-featured', available: '2026-10-24' },
    { id: 'had-its-turn', available: '2026-10-06' },
  ];

  it('drops candidates that have ever held a rail slot', () => {
    expect(excludeRetired(candidates, new Set(['had-its-turn'])))
      .toEqual([{ id: 'never-featured', available: '2026-10-24' }]);
  });

  it('keeps everything when nothing has been featured', () => {
    expect(excludeRetired(candidates, new Set())).toEqual(candidates);
  });
});

/**
 * The invariant, against the entries actually in the repo.
 *
 * index.astro filters self-amplification and then slices to 8, so a ninth flag
 * or a flag the filter drops renders a short rail in silence. Until now the
 * only thing standing between that and production was a grep I ran by hand at
 * the end of the sidebar job. This runs in the pre-commit hook.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

describe('the committed rail', () => {
  it('matches what the site will render', () => {
    const dir = resolve(__dirname, '..', 'content', 'entries');
    const entries = readdirSync(dir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => JSON.parse(readFileSync(resolve(dir, f), 'utf8')));
    // A test that loaded nothing would pass this silently, which is the shape
    // of the quote gate that verified 25 of 871 entries and exited 0.
    expect(entries.length).toBeGreaterThan(500);
    expect(railInvariantProblems(entries)).toEqual([]);
  });
});

describe('when a candidate became available to the rail', () => {
  // `available` decided pass-over counts, and for a future-dated entry it was
  // set to the START OF THE WINDOW — so an entry that shipped today was
  // reported as passed over by every change since 1 October. On 2026-11-01 the
  // Spanish edition, committed that morning, topped the list at 20x: the exact
  // number of recorded changes, i.e. the maximum the report can produce. The
  // strongest signal in the report was manufactured, and it pointed at the
  // newest entries rather than the longest-waiting ones.
  it('a future-dated entry is available from the day it shipped, not the window start', () => {
    expect(availableFrom({ id: 'x', date: '2026-11-25' }, '2026-10-01', '2026-11-01'))
      .toBe('2026-11-01');
  });

  it('an entry shipped later than its own date is available from the ship day', () => {
    // Kass Lazerow is dated 2026-10-07 and was committed on the 9th.
    expect(availableFrom({ id: 'x', date: '2026-10-07', shipped: '2026-10-09' },
                         '2026-10-01', '2026-11-01')).toBe('2026-10-09');
  });

  it('an entry shipped the day it happened is available that day', () => {
    expect(availableFrom({ id: 'x', date: '2026-10-05', shipped: '2026-10-05' },
                         '2026-10-01', '2026-11-01')).toBe('2026-10-05');
  });

  it('falls back to the entry date when the ship day is unknown', () => {
    expect(availableFrom({ id: 'x', date: '2026-10-05' }, '2026-10-01', '2026-11-01'))
      .toBe('2026-10-05');
  });
});

/**
 * On 2026-11-06 the report's candidate list showed twelve rows, the oldest
 * entry on it dated 2026-10-29, and nine un-featured standalone entries newer
 * than that did not appear at all — including the Thinkers50 London Summit
 * entry that took the slot SOSV vacated that night. Two filters combined to do
 * it: `counts[id] > 0` dropped anything no recorded rail change had yet passed
 * over, and `slice(0, 12)` on a list sorted by count descending cut from the
 * fresh end. A report built so the rail could not go stale was hiding the
 * newest candidates by construction.
 *
 * So: every candidate, newest first, count as annotation — which is what the
 * prompt already says the count is.
 */
describe('rankForReport', () => {
  const cands = [
    { id: '2026-11-02-thinkers50', available: '2026-11-02' },
    { id: '2026-10-05-amazon-1', available: '2026-10-05' },
    { id: '2026-11-05-wgbt', available: '2026-11-05' },
  ];
  const counts = { '2026-11-02-thinkers50': 2, '2026-10-05-amazon-1': 18, '2026-11-05-wgbt': 0 };

  it('keeps a candidate no rail change has passed over yet', () => {
    expect(rankForReport(cands, counts).map((c) => c.id)).toContain('2026-11-05-wgbt');
  });

  it('returns every candidate, with nothing truncated', () => {
    expect(rankForReport(cands, counts)).toHaveLength(3);
  });

  it('orders newest first, not by pass-over count', () => {
    expect(rankForReport(cands, counts).map((c) => c.id)).toEqual([
      '2026-11-05-wgbt',
      '2026-11-02-thinkers50',
      '2026-10-05-amazon-1',
    ]);
  });

  it('breaks a date tie on id so the order is stable run to run', () => {
    const tied = [
      { id: '2026-11-02-zzz', available: '2026-11-02' },
      { id: '2026-11-02-aaa', available: '2026-11-02' },
    ];
    expect(rankForReport(tied, { '2026-11-02-zzz': 1, '2026-11-02-aaa': 1 }).map((c) => c.id)).toEqual([
      '2026-11-02-aaa',
      '2026-11-02-zzz',
    ]);
  });
});

/**
 * A report that omits a candidate produces no symptom. On 2026-11-06 the rail
 * was full, the invariant passed, and nine candidates were missing from the
 * listing — visible only by enumerating the entries independently, which is the
 * work the report exists to replace. So the report states its own arithmetic and
 * fails when the parts do not add up, the same way the quote gate had to start
 * reporting coverage rather than only failures.
 */
describe('candidateReconciliation', () => {
  it('reconciles when every standalone entry is accounted for', () => {
    expect(
      candidateReconciliation({ standalone: 38, featured: 8, retired: 17, shown: 13 })
    ).toBeNull();
  });

  it('reports the shortfall when candidates went missing', () => {
    const problem = candidateReconciliation({ standalone: 38, featured: 8, retired: 17, shown: 4 });
    expect(problem).toMatch(/9/);
    expect(problem).toMatch(/13/);
  });

  it('reports a surplus too — a double-counted candidate is just as wrong', () => {
    expect(candidateReconciliation({ standalone: 38, featured: 8, retired: 17, shown: 20 })).toBeTruthy();
  });
});
