import { describe, it, expect } from 'vitest';
import {
  isoWeek,
  groupQuotesByWeek,
  interleaveChorus,
  type ReaderQuote,
} from '../src/lib/reader-quotes';

const q = (date: string, quote: string, author = 'A', url = `https://x/${quote}`): ReaderQuote => ({
  quote, author, title: '', url, date,
});

const entry = (id: string, date: string) => ({ id, date }) as any;

// ── ISO week keys ────────────────────────────────────────────────────────

describe('isoWeek', () => {
  it('gives the same key to days in the same Mon-Sun week', () => {
    // 2026-10-05 is a Monday; 2026-10-11 the Sunday that closes that week.
    expect(isoWeek('2026-10-05')).toBe(isoWeek('2026-10-07'));
    expect(isoWeek('2026-10-05')).toBe(isoWeek('2026-10-11'));
  });

  it('starts a new key on the next Monday', () => {
    expect(isoWeek('2026-10-11')).not.toBe(isoWeek('2026-10-12'));
  });

  it('is sortable as a string, including across a year boundary', () => {
    const keys = ['2026-12-28', '2027-01-04', '2026-11-02'].map(isoWeek);
    expect([...keys].sort()).toEqual([isoWeek('2026-11-02'), isoWeek('2026-12-28'), isoWeek('2027-01-04')]);
  });
});

// ── grouping ─────────────────────────────────────────────────────────────

describe('groupQuotesByWeek', () => {
  it('buckets quotes into their week, newest week first', () => {
    const g = groupQuotesByWeek([
      q('2026-09-28', 'older'),
      q('2026-10-07', 'newer'),
    ]);
    expect(g.map(b => b.quotes[0].quote)).toEqual(['newer', 'older']);
  });

  it('drops quotes with no date or no quote text', () => {
    const g = groupQuotesByWeek([
      q('2026-10-07', 'keep'),
      { quote: '', author: 'B', title: '', url: 'u', date: '2026-10-07' },
      { quote: 'nodate', author: 'C', title: '', url: 'u2', date: '' },
    ]);
    expect(g.flatMap(b => b.quotes).map(x => x.quote)).toEqual(['keep']);
  });

  it('dedupes on url, keeping the first occurrence', () => {
    const g = groupQuotesByWeek([
      q('2026-10-07', 'first', 'A', 'https://same'),
      q('2026-10-07', 'second', 'B', 'https://same'),
    ]);
    expect(g.flatMap(b => b.quotes)).toHaveLength(1);
    expect(g[0].quotes[0].quote).toBe('first');
  });

  it('sorts quotes inside a week newest-first so the band leads with the latest', () => {
    const g = groupQuotesByWeek([q('2026-10-06', 'mon'), q('2026-10-08', 'wed')]);
    expect(g[0].quotes.map(x => x.quote)).toEqual(['wed', 'mon']);
  });
});

// ── interleaving into the timeline ───────────────────────────────────────

describe('interleaveChorus', () => {
  const entries = [entry('e1', '2026-10-13'), entry('e2', '2026-10-06'), entry('e3', '2026-09-29')];

  it('emits entries in their original order when there are no quotes', () => {
    const out = interleaveChorus(entries, []);
    expect(out.map(x => x.kind)).toEqual(['entry', 'entry', 'entry']);
  });

  it('places a band after the last entry of the week it covers', () => {
    // A quote from the week of Oct 5-11 belongs after e2 (Oct 6), not after e1.
    const out = interleaveChorus(entries, [q('2026-10-07', 'hi')]);
    const kinds = out.map(x => x.kind);
    const bandAt = kinds.indexOf('chorus');
    expect(out[bandAt - 1]).toMatchObject({ kind: 'entry', entry: { id: 'e2' } });
  });

  it('never emits two bands for the same week', () => {
    const out = interleaveChorus(entries, [q('2026-10-06', 'a'), q('2026-10-08', 'b')]);
    expect(out.filter(x => x.kind === 'chorus')).toHaveLength(1);
  });

  it('drops a week whose quotes have nowhere to attach', () => {
    // No entry falls in the week of 2026-08-10, so that band would float.
    const out = interleaveChorus(entries, [q('2026-08-12', 'orphan')]);
    expect(out.filter(x => x.kind === 'chorus')).toHaveLength(0);
  });

  it('carries every quote of the week into its band', () => {
    const out = interleaveChorus(entries, [q('2026-10-06', 'a'), q('2026-10-08', 'b')]);
    const band = out.find(x => x.kind === 'chorus') as any;
    expect(band.quotes).toHaveLength(2);
  });

  it('is stable: entry order is never reordered by interleaving', () => {
    const out = interleaveChorus(entries, [q('2026-10-07', 'x'), q('2026-09-30', 'y')]);
    expect(out.filter(x => x.kind === 'entry').map((x: any) => x.entry.id))
      .toEqual(['e1', 'e2', 'e3']);
  });
});
