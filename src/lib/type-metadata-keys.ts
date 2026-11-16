/**
 * Every `type_metadata` key this site knows about, and what reads it.
 *
 * WHY THIS EXISTS
 *
 * `type_metadata` is an untyped `Record<string, unknown>` shared by every entry
 * type. Nothing enumerated the keys, so nothing could tell a real key from a
 * forgotten one, a typo, or an invention. Measured 2026-11-16: 42 distinct keys
 * in use, 22 read by some component and 20 read by nothing at all — including
 * `audience`, set on 79 entries and rendered nowhere, and `venue`, a three-use
 * near-duplicate of `city` (50 uses).
 *
 * That silence is what let the book-tour strip go stale. `UpcomingStrip.astro`
 * renders an event only when `city` is set; two events shipped without it, the
 * strip's forward edge froze at one card, and every other surface looked
 * correct. A missing key and a misspelt key produce the same result as a key
 * that was never meant to be there: nothing.
 *
 * The registry does not make a key required — requirements differ per entry
 * type and `city` genuinely should be absent on a virtual event. It makes the
 * SET closed, so `citi`, `City` or a freshly invented `location` fails a test
 * instead of being silently ignored for months.
 *
 * Adding a key is deliberate: add it here with its consumer, or with
 * `unread` and a reason.
 */

/** Keys a component or script actually reads. */
export const CONSUMED_KEYS: Record<string, string> = {
  amazon_badge: 'index.astro',
  amazon_category: 'index.astro',
  amazon_rank: 'index.astro',
  award_curator: 'UpcomingStrip.astro, index.astro',
  award_label: 'UpcomingStrip.astro, index.astro',
  award_priority: 'index.astro',
  award_side: 'index.astro',
  city: 'UpcomingStrip.astro — the book-tour strip filters on it',
  compact: 'TimelineEntry.astro',
  details: 'TimelineEntry.astro',
  event_photos: 'TimelineEntry.astro',
  face_position: 'UpcomingStrip.astro',
  featured: 'index.astro — the What\'s New rail',
  hero_quote_author: 'index.astro',
  hero_quote_label: 'index.astro',
  highlight: 'UpcomingStrip.astro — the faces row',
  image_bg: 'TimelineEntry.astro',
  image_fit: 'TimelineEntry.astro',
  sidebar_quote: 'index.astro',
  signup_url: 'UpcomingStrip.astro — renders the RSVP link',
  weight: 'TimelineEntry.astro',
};

/**
 * Keys written by the scanners that no component reads.
 *
 * Kept rather than deleted: some are real data a future surface or the social
 * agent may want, and deleting a field across hundreds of entries to tidy a
 * list is a worse trade than listing it. But writing one is not publishing it,
 * which is worth knowing before spending a cycle populating one.
 */
export const UNREAD_KEYS: Record<string, string> = {
  agenda_url: 'one event; nothing renders it',
  amazon_url: 'superseded by the rank fields index.astro reads',
  audience: 'set on 79 entries by the scan prompts; rendered nowhere',
  average_rating: 'Goodreads snapshot data',
  co_speakers: 'who else was on the bill; no surface shows it',
  episode_length: 'podcast duration',
  episode_number: 'podcast numbering',
  language: 'foreign editions',
  moderator: 'one event',
  podcast_show: 'show name; the card uses POSTER_LABELS instead',
  publication: 'one entry',
  publisher: 'foreign editions',
  review_count: 'Goodreads snapshot data',
  room: 'event room number',
  session: 'event session name',
  session_time: 'event session time',
  session_title: 'event session title',
  time: 'event time of day; the card shows the date only',
  translation: 'foreign editions',
  translator: 'foreign editions — named in the summary instead',
  venue: 'near-duplicate of city; prefer city, which the strip reads',
};

/** The closed set. A key outside this fails `type-metadata-keys.test.ts`. */
export const KNOWN_KEYS: ReadonlySet<string> = new Set([
  ...Object.keys(CONSUMED_KEYS),
  ...Object.keys(UNREAD_KEYS),
]);

export interface UnknownKeyUse {
  file: string;
  key: string;
}

/** Keys used by an entry that are not in the registry. */
export function findUnknownKeys(
  entries: { file: string; type_metadata?: Record<string, unknown> | null }[],
): UnknownKeyUse[] {
  const out: UnknownKeyUse[] = [];
  for (const e of entries) {
    for (const key of Object.keys(e.type_metadata ?? {})) {
      if (!KNOWN_KEYS.has(key)) out.push({ file: e.file, key });
    }
  }
  return out;
}
