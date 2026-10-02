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

/**
 * Surfaces Eric controls. Used to tell self-amplification apart from
 * third-party coverage that happens to quote him.
 *
 * Matching is anchored (`/in/eries`, `/posts/eries_`, `/ericries/`) so a
 * different person whose handle merely contains "eries" doesn't match.
 */
const ERIC_HOSTS = new Set(['incorruptible.co', 'theleanstartup.com']);

export function isEricVenue(sourceUrl: string | null | undefined): boolean {
  if (!sourceUrl) return false;
  let url: URL;
  try {
    url = new URL(sourceUrl);
  } catch {
    return false;
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, '');
  const path = url.pathname.toLowerCase();

  if (ERIC_HOSTS.has(host)) return true;
  if (host === 'linkedin.com') return path.startsWith('/in/eries') || path.startsWith('/posts/eries_');
  if (host === 'x.com' || host === 'twitter.com') return path.startsWith('/ericries/');
  if (host === 'tiktok.com') return path.startsWith('/@ericriesactual');
  return false;
}

/**
 * True only when Eric is BOTH the quoted speaker AND the venue is his own —
 * i.e. the entry is Eric amplifying himself on his own channel.
 *
 * Deliberately NOT just "is Eric the speaker": that also catches every
 * podcast, interview and press piece, which are third-party momentum even
 * though Eric is the one talking. See
 * docs/postmortems/2026-10-02-whats-new-excluded-third-party-media.md
 */
export function isSelfAmplification(entry: {
  blockquote_source?: string | null;
  source_url?: string | null;
}): boolean {
  const speakerIsEric = (entry.blockquote_source || '').startsWith('Eric Ries');
  return speakerIsEric && isEricVenue(entry.source_url);
}
