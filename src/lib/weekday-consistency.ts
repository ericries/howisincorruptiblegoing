/**
 * A weekday named in an entry must agree with that entry's date.
 *
 * Three of these shipped before anything checked: the Berkeley Newton lecture
 * said "Monday October 27" (a Tuesday), Rotman said "Monday August 18" (a
 * Tuesday), Quebec House said "Sunday September 7" (a Monday). Each was a
 * weekday asserted by eye, and on the day two of them were corrected the prompt
 * already carried a line telling me to compute weekdays instead of eyeballing
 * them. The instruction was not the missing piece; a check was.
 */

const WEEKDAYS = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday',
  'Thursday', 'Friday', 'Saturday',
] as const;

// Word-bounded so "Sundays with the board" and "Fridays" do not match.
const WEEKDAY_RE = new RegExp(`\\b(${WEEKDAYS.join('|')})\\b`);

/**
 * Fields worth checking.
 *
 * `summary` is deliberately excluded: prose there can legitimately name a
 * different day than the entry's own ("she spent Monday filling thirty pages of
 * notes" on a Friday-dated entry). Including it produced a false positive on the
 * first run. `attribution_title` is where an event's datetime actually lives, so
 * it is the field that matters most.
 */
const CHECKED_FIELDS = ['title', 'attribution_title'] as const;

export interface WeekdayMismatch {
  file: string;
  field: string;
  named: string;
  actual: string;
  date: string;
}

export function findWeekdayMismatches(
  entries: Array<{
    file: string;
    date?: string | null;
    title?: string | null;
    attribution_title?: string | null;
    summary?: string | null;
  }>
): WeekdayMismatch[] {
  const out: WeekdayMismatch[] = [];

  for (const e of entries) {
    const raw = (e.date || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) continue;      // malformed date: not our failure to report
    // Parse as UTC so a local timezone west of Greenwich cannot shift the day.
    const when = new Date(`${raw}T00:00:00Z`);
    if (Number.isNaN(when.getTime())) continue;
    const actual = WEEKDAYS[when.getUTCDay()];

    for (const field of CHECKED_FIELDS) {
      const value = (e as Record<string, unknown>)[field];
      if (typeof value !== 'string' || !value) continue;
      const m = WEEKDAY_RE.exec(value);
      if (!m) continue;
      if (m[1] !== actual) {
        out.push({ file: e.file, field, named: m[1], actual, date: raw });
      }
    }
  }

  return out;
}
