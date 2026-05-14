import { describe, it, expect } from 'vitest';
import { loadEntries, partitionReactions } from '../src/lib/entries';
import type { TimelineEntry } from '../src/lib/schema';
import * as path from 'path';

const entriesDir = path.join(process.cwd(), 'content', 'entries');

describe('loadEntries', () => {
  it('loads and parses all JSON files from a directory', () => {
    const entries = loadEntries(entriesDir);
    expect(entries.length).toBeGreaterThanOrEqual(2);
  });

  it('sorts entries by date descending (newest first)', () => {
    const entries = loadEntries(entriesDir);
    expect(entries[0].date >= entries[1].date).toBe(true);
  });

  it('returns typed TimelineEntry objects', () => {
    const entries = loadEntries(entriesDir);
    const entry = entries[0];
    expect(entry).toHaveProperty('id');
    expect(entry).toHaveProperty('type');
    expect(entry).toHaveProperty('summary');
    expect(entry).toHaveProperty('blockquote');
  });
});

describe('partitionReactions', () => {
  function mkEntry(overrides: Partial<TimelineEntry>): TimelineEntry {
    return {
      id: 'x', date: '2026-04-07', type: 'event', title: 't', summary: 's',
      blockquote: 'b', blockquote_source: 'src', source_url: 'https://e.com',
      source_urls: null, video_url: null, image: null,
      attribution: null, attribution_title: null, attribution_image: null,
      tags: ['t'], type_metadata: {}, scanner_source: 'manual',
      verified: true, created_at: '2026-04-07T00:00:00Z',
      ...overrides,
    } as TimelineEntry;
  }

  it('separates reactions from main feed', () => {
    const entries = [
      mkEntry({ id: '2026-04-07-parent', type: 'event' }),
      mkEntry({ id: '2026-04-08-child', type: 'reaction', parent_id: '2026-04-07-parent', date: '2026-04-08' }),
    ];
    const { main, reactionsByParent } = partitionReactions(entries);
    expect(main).toHaveLength(1);
    expect(main[0].id).toBe('2026-04-07-parent');
    expect(reactionsByParent.get('2026-04-07-parent')).toHaveLength(1);
  });

  it('sorts reactions within a parent cluster by date ascending', () => {
    const entries = [
      mkEntry({ id: '2026-04-07-parent', type: 'event' }),
      mkEntry({ id: '2026-04-09-late', type: 'reaction', parent_id: '2026-04-07-parent', date: '2026-04-09' }),
      mkEntry({ id: '2026-04-08-early', type: 'reaction', parent_id: '2026-04-07-parent', date: '2026-04-08' }),
    ];
    const { reactionsByParent } = partitionReactions(entries);
    const cluster = reactionsByParent.get('2026-04-07-parent')!;
    expect(cluster.map(r => r.id)).toEqual(['2026-04-08-early', '2026-04-09-late']);
  });

  it('groups reactions by parent_id', () => {
    const entries = [
      mkEntry({ id: 'p1', type: 'event' }),
      mkEntry({ id: 'p2', type: 'event' }),
      mkEntry({ id: 'r1a', type: 'reaction', parent_id: 'p1' }),
      mkEntry({ id: 'r1b', type: 'reaction', parent_id: 'p1' }),
      mkEntry({ id: 'r2', type: 'reaction', parent_id: 'p2' }),
    ];
    const { reactionsByParent } = partitionReactions(entries);
    expect(reactionsByParent.get('p1')).toHaveLength(2);
    expect(reactionsByParent.get('p2')).toHaveLength(1);
  });

  it('drops reactions that lack a parent_id (orphans)', () => {
    const entries = [
      mkEntry({ id: 'p1', type: 'event' }),
      mkEntry({ id: 'orphan', type: 'reaction', parent_id: null }),
    ];
    const { main, reactionsByParent } = partitionReactions(entries);
    expect(main.map(m => m.id)).toEqual(['p1']);
    expect(reactionsByParent.size).toBe(0);
  });
});
