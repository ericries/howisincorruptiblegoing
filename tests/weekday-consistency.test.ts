import { describe, it, expect } from 'vitest';
import { findWeekdayMismatches } from '../src/lib/weekday-consistency';

/**
 * A weekday named in an entry must match the entry's own date.
 *
 * Three of these shipped. The Berkeley Newton lecture said "Monday October 27"
 * when Oct 27 is a Tuesday; Rotman said "Monday August 18" (a Tuesday); Quebec
 * House said "Sunday September 7" (a Monday). Each was a weekday asserted by
 * eye, and the prompt line telling me to compute it instead was already there
 * on the day two of the three were written.
 *
 * Scope is `title` and `attribution_title` only. A summary can legitimately name
 * a different day — "she spent Monday reading it" on a Friday-dated entry is
 * fine — so including it produced a false positive immediately.
 */
describe('findWeekdayMismatches', () => {
  it('flags a weekday that contradicts the date', () => {
    const bad = findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-27', attribution_title: 'Berkeley · Monday October 27, 2026' },
    ]);
    expect(bad).toHaveLength(1);
    expect(bad[0].named).toBe('Monday');
    expect(bad[0].actual).toBe('Tuesday');
    expect(bad[0].field).toBe('attribution_title');
  });

  it('passes a weekday that matches', () => {
    expect(findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-27', attribution_title: 'Berkeley · Tuesday October 27, 2026' },
    ])).toEqual([]);
  });

  it('checks the title as well as the attribution', () => {
    // 2026-10-23 is a Friday.
    const bad = findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-23', title: 'Thursday roundtable' },
    ]);
    expect(bad).toHaveLength(1);
    expect(bad[0].field).toBe('title');
    expect(bad[0].actual).toBe('Friday');
  });

  it('judges only the first weekday in a field, so a second one can be another day', () => {
    // "Friday ... moved to Thursday" on a Friday-dated entry is a true sentence;
    // the day that labels the entry is the one it leads with.
    expect(findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-23', title: 'Friday roundtable, moved from Thursday' },
    ])).toEqual([]);
  });

  it('ignores the summary, where another day can be meant legitimately', () => {
    expect(findWeekdayMismatches([
      { file: 'x.json', date: '2026-09-25', summary: 'She spent Monday filling thirty pages of notes.' },
    ])).toEqual([]);
  });

  it('ignores entries that name no weekday', () => {
    expect(findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-27', attribution_title: 'Berkeley · October 27, 2026' },
    ])).toEqual([]);
  });

  it('does not match a weekday inside a longer word', () => {
    expect(findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-27', title: 'Sundays with the board' },
    ])).toEqual([]);
  });

  it('survives a malformed date rather than throwing', () => {
    expect(findWeekdayMismatches([
      { file: 'x.json', date: 'not-a-date', attribution_title: 'Monday' },
    ])).toEqual([]);
  });

  it('reports every offending field on one entry', () => {
    const bad = findWeekdayMismatches([
      { file: 'x.json', date: '2026-10-27', title: 'Monday talk', attribution_title: 'Monday, Berkeley' },
    ]);
    expect(bad).toHaveLength(2);
  });
});
