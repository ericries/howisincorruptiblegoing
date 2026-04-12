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
