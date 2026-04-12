import { describe, it, expect } from 'vitest';
import { loadEntries } from '../src/lib/entries';
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
