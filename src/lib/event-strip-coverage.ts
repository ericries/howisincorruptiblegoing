/**
 * The book-tour strip renders an event only if it carries
 * `type_metadata.city` — UpcomingStrip.astro filters on it, because the strip
 * is in-person stops and a card with no place is not a stop.
 *
 * Nothing checked that the field was there. So an event shipped without a city
 * was missing from the strip and correct everywhere else: its own page, the
 * What's New rail, the timeline. On 2026-11-16 Eric noticed the strip had
 * "stopped updating", and it had — ZEBRAHOOD (Tokyo, 27 Nov) and Yale SOM 50
 * (New Haven, 2 Dec) both shipped that day with no city, leaving the forward
 * edge as one card, Corporate Rebels on the 19th. Two months of events had
 * been landing with the field unset and no signal anywhere.
 *
 * This is scoped to FUTURE events on purpose. 19 past events had no city when
 * this was written, mostly LinkedIn Lives and livestreams that never needed
 * one; reporting those on every commit would make the check noise, and noise
 * gets ignored. A future event is the thing Eric actually looks at, and
 * keeping the check narrow is what keeps it readable at zero.
 */

/** Declared-virtual events legitimately have no city. */
const VIRTUAL_RE = /\b(virtual|online|zoom|webinar|remote|livestream|linkedin live)\b/i;

export interface EventLike {
  file: string;
  type?: string;
  date?: string;
  title?: string;
  attribution_title?: string;
  summary?: string;
  type_metadata?: Record<string, unknown> | null;
}

export interface StripGap {
  file: string;
  date: string;
  title: string;
}

/**
 * Future `event` entries that will not render in the book-tour strip because
 * they carry no `type_metadata.city`, excluding ones that say they are virtual.
 *
 * `today` is passed in rather than read from the clock so the test can pin a
 * date — the same reason scan_catchup takes its own `now`.
 */
export function findEventsMissingFromStrip(
  entries: EventLike[],
  today: string,
): StripGap[] {
  const out: StripGap[] = [];
  for (const e of entries) {
    if (e.type !== 'event') continue;
    const date = e.date ?? '';
    // Strictly after today: an event dated today has already happened or is
    // happening, and needs no RSVP card.
    if (!(date > today)) continue;
    const meta = e.type_metadata ?? {};
    const city = meta['city'];
    if (typeof city === 'string' && city.length > 0) continue;
    const blob = [e.title, e.attribution_title, e.summary]
      .filter((s): s is string => typeof s === 'string').join(' ');
    if (VIRTUAL_RE.test(blob)) continue;
    out.push({ file: e.file, date, title: e.title ?? '' });
  }
  return out;
}
