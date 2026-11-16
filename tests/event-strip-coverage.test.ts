import { describe, it, expect } from 'vitest';
import { findEventsMissingFromStrip } from '../src/lib/event-strip-coverage';

/**
 * The book-tour strip renders an event only if it carries
 * `type_metadata.city`. Nothing checked that, so an event shipped without a
 * city was invisible there and nowhere else — the entry page looked right, the
 * What's New rail looked right, and only the strip was wrong.
 *
 * On 2026-11-16 Eric noticed it had "stopped updating". It had: ZEBRAHOOD
 * (Tokyo, 27 Nov) and Yale SOM 50 (New Haven, 2 Dec) had both shipped that day
 * with no city, so the strip's forward edge was a single card — Corporate
 * Rebels on the 19th — and looked frozen.
 *
 * Scope is deliberately FUTURE events only. A past event missing a city is a
 * cosmetic backlog item; a future one is the symptom Eric actually sees, and
 * keeping the check narrow is what keeps it at zero and therefore worth
 * reading. Genuinely virtual events have no city by design, so a declared
 * virtual event is not a finding.
 */
describe('findEventsMissingFromStrip', () => {
  const today = '2026-11-16';

  it('flags a future in-person event with no city', () => {
    const out = findEventsMissingFromStrip([
      {
        file: 'zebrahood.json', type: 'event', date: '2026-11-27',
        title: 'ZEBRAHOOD 2026 (Tokyo)',
        attribution_title: 'Home Work Village, Setagaya, Tokyo',
        type_metadata: {},
      },
    ], today);
    expect(out.map((o) => o.file)).toEqual(['zebrahood.json']);
  });

  it('passes a future event that has a city', () => {
    expect(findEventsMissingFromStrip([
      {
        file: 'yale.json', type: 'event', date: '2026-12-02',
        title: 'Yale SOM 50', attribution_title: 'Evans Hall, New Haven',
        type_metadata: { city: 'New Haven' },
      },
    ], today)).toEqual([]);
  });

  it('does not flag a declared virtual event', () => {
    // SOSV Deep Tech Summit: "Free and virtual" — correctly has no city.
    expect(findEventsMissingFromStrip([
      {
        file: 'sosv.json', type: 'event', date: '2026-11-20',
        title: 'SOSV Deep Tech Summit',
        attribution_title: 'Free and virtual · November 4-6, 2026',
        type_metadata: {},
      },
    ], today)).toEqual([]);
  });

  it('does not flag a past event, however bare', () => {
    // 19 of these existed on 2026-11-16, mostly LinkedIn Lives. Reporting them
    // every commit would make the check noise, and noise gets ignored.
    expect(findEventsMissingFromStrip([
      {
        file: 'old.json', type: 'event', date: '2026-03-12',
        title: 'Unshackled LinkedIn Live', attribution_title: '',
        type_metadata: {},
      },
    ], today)).toEqual([]);
  });

  it('ignores non-event types', () => {
    expect(findEventsMissingFromStrip([
      {
        file: 'pod.json', type: 'podcast', date: '2026-12-01',
        title: 'Some episode', attribution_title: '', type_metadata: {},
      },
    ], today)).toEqual([]);
  });

  it('treats an event dated today as not yet future', () => {
    // The HBS guest slot was dated 2026-11-16 and joined by Zoom; an event on
    // today's date is already decided and does not need an RSVP card.
    expect(findEventsMissingFromStrip([
      {
        file: 'hbs.json', type: 'event', date: today,
        title: 'Launching Tech Ventures', attribution_title: 'HBS',
        type_metadata: {},
      },
    ], today)).toEqual([]);
  });
});

/**
 * The seam, read from the real corpus.
 *
 * The unit tests above all passed while the lint wiring was broken: lint
 * builds a PROJECTION of each entry (file, type, date, id, parent_id,
 * source_url) and I spread that into the checker, so `type_metadata` and
 * `title` arrived undefined and all three future events were reported as
 * missing a city — including the two that had just been given one. A test on
 * synthetic objects with the right shape cannot see that; only reading the
 * files the way the site reads them can.
 */
describe('the real corpus', () => {
  it('has no future event that would be missing from the strip', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const dir = path.join(process.cwd(), 'content', 'entries');
    const entries = fs.readdirSync(dir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => ({ file: f, ...JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')) }));

    const today = new Date().toISOString().slice(0, 10);
    const gaps = findEventsMissingFromStrip(entries, today);
    expect(gaps, `these future events carry no type_metadata.city, so the ` +
      `book-tour strip will not show them: ` +
      gaps.map((g) => `${g.date} ${g.file}`).join(', ')).toEqual([]);
  });

  it('renders every future event in the strip with a city', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const dir = path.join(process.cwd(), 'content', 'entries');
    const today = new Date().toISOString().slice(0, 10);
    const future = fs.readdirSync(dir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')))
      .filter((e) => e.type === 'event' && e.date > today);
    // Every future event is either placed or declared virtual. If this ever
    // fails, the strip's forward edge is about to go stale again.
    for (const e of future) {
      const city = (e.type_metadata ?? {})['city'];
      const blob = `${e.title ?? ''} ${e.attribution_title ?? ''} ${e.summary ?? ''}`;
      const virtual = /\b(virtual|online|zoom|webinar|remote|livestream|linkedin live)\b/i.test(blob);
      expect(Boolean(city) || virtual, `${e.id} has neither a city nor a virtual marker`).toBe(true);
    }
  });
});
