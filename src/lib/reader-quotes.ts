/**
 * Reader quotes — the "chorus band" on the timeline.
 *
 * Short superlative comments collected by the daily LinkedIn comment scan. The
 * full archive lives in data/archive/linkedin-comments/ (gitignored, ~88 and
 * growing); only a curated subset is promoted into data/reader-quotes.json and
 * published here.
 *
 * The band is deliberately unattached: it renders between dated entries with no
 * card, no shadow and no dot in the rail, so it never occupies an event slot.
 * That is the whole point — see docs/postmortems and the design note from
 * 2026-10-07. A `reaction` claims "this is a response to THIS event"; most of
 * these answer one of Eric's posts, so that claim would be false.
 */

export interface ReaderQuote {
  quote: string;
  author: string;
  title: string;
  url: string;
  /** YYYY-MM-DD, the day the comment was posted. */
  date: string;
}

export interface ChorusWeek {
  /** Sortable Monday-anchored key, e.g. "2026-W41". */
  week: string;
  quotes: ReaderQuote[];
}

export type TimelineSlot =
  | { kind: 'entry'; entry: { id: string; date: string } }
  | { kind: 'chorus'; week: string; quotes: ReaderQuote[] };

/**
 * Monday-anchored ISO-ish week key. Built from the Monday's calendar date
 * rather than a week number, so it sorts lexicographically and stays correct
 * across a year boundary without any 52/53-week edge cases.
 */
export function isoWeek(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return '';
  // getUTCDay(): 0=Sun. Shift so Monday starts the week.
  const dayFromMonday = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - dayFromMonday);
  return d.toISOString().slice(0, 10);
}

/** Bucket quotes by week, newest week first, newest quote first inside a week. */
export function groupQuotesByWeek(quotes: ReaderQuote[]): ChorusWeek[] {
  const seen = new Set<string>();
  const byWeek = new Map<string, ReaderQuote[]>();

  for (const q of quotes) {
    if (!q?.quote?.trim() || !q?.date) continue;
    const week = isoWeek(q.date);
    if (!week) continue;
    const key = q.url || `${q.author}|${q.quote}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const list = byWeek.get(week) ?? [];
    list.push(q);
    byWeek.set(week, list);
  }

  return [...byWeek.entries()]
    .map(([week, qs]) => ({
      week,
      quotes: qs.sort((a, b) => b.date.localeCompare(a.date)),
    }))
    .sort((a, b) => b.week.localeCompare(a.week));
}

/**
 * Walk the (already date-sorted, newest-first) entry list and drop each week's
 * band immediately after the LAST entry belonging to that week — i.e. just
 * before the timeline moves into an older week.
 *
 * A week with no entry to anchor to is dropped rather than floated; a band with
 * nothing above it reads as a header for the entries below, which is wrong.
 */
export function interleaveChorus(
  entries: { id: string; date: string }[],
  quotes: ReaderQuote[],
): TimelineSlot[] {
  const weeks = new Map(groupQuotesByWeek(quotes).map(w => [w.week, w.quotes]));
  const out: TimelineSlot[] = [];

  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    out.push({ kind: 'entry', entry: e });

    const week = isoWeek(e.date);
    const pending = weeks.get(week);
    if (!pending) continue;

    // Only emit once this is the last entry of its week.
    const next = entries[i + 1];
    if (next && isoWeek(next.date) === week) continue;

    out.push({ kind: 'chorus', week, quotes: pending });
    weeks.delete(week);
  }

  return out;
}
