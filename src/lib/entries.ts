import * as fs from 'fs';
import * as path from 'path';
import type { TimelineEntry } from './schema';

export function loadEntries(entriesDir: string): TimelineEntry[] {
  if (!fs.existsSync(entriesDir)) {
    return [];
  }

  const files = fs.readdirSync(entriesDir).filter((f) => f.endsWith('.json'));

  const entries: TimelineEntry[] = files.map((file) => {
    const filePath = path.join(entriesDir, file);
    const contents = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(contents) as TimelineEntry;
  });

  // Sort by date descending (newest first)
  entries.sort((a, b) => b.date.localeCompare(a.date));

  return entries;
}

/**
 * Split a flat list of entries into (a) the main timeline feed (no reactions)
 * and (b) a parent_id → reactions[] map, with each cluster sorted by date asc.
 *
 * Used by the homepage and any other surface that needs to render reactions
 * clustered under their parent rather than inline on the timeline.
 */
export function partitionReactions(entries: TimelineEntry[]): {
  main: TimelineEntry[];
  reactionsByParent: Map<string, TimelineEntry[]>;
} {
  const reactionsByParent = new Map<string, TimelineEntry[]>();
  const main: TimelineEntry[] = [];
  for (const e of entries) {
    if (e.type === 'reaction' && e.parent_id) {
      const list = reactionsByParent.get(e.parent_id) ?? [];
      list.push(e);
      reactionsByParent.set(e.parent_id, list);
    } else if (e.type !== 'reaction') {
      main.push(e);
    }
    // Drop orphan reactions (type=reaction with no parent_id) — lint should catch these
  }
  for (const list of reactionsByParent.values()) {
    list.sort((a, b) => a.date.localeCompare(b.date));
  }
  return { main, reactionsByParent };
}
