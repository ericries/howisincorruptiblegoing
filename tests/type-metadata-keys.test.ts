import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import {
  findUnknownKeys, KNOWN_KEYS, CONSUMED_KEYS, UNREAD_KEYS,
} from '../src/lib/type-metadata-keys';

/**
 * `type_metadata` was an open bag. A key could be forgotten, misspelt or
 * invented and all three produced the same thing: silence. That is how the
 * book-tour strip went stale — two events shipped without `city`, which
 * UpcomingStrip.astro filters on, and every other surface looked right.
 *
 * Closing the set does not make any key required (a virtual event correctly
 * has no city). It makes a key outside the registry fail here rather than be
 * ignored for months.
 */
describe('type_metadata key registry', () => {
  it('flags a key that is not in the registry', () => {
    expect(findUnknownKeys([
      { file: 'e.json', type_metadata: { citi: 'Tokyo' } },
    ])).toEqual([{ file: 'e.json', key: 'citi' }]);
  });

  it('accepts a registered key', () => {
    expect(findUnknownKeys([
      { file: 'e.json', type_metadata: { city: 'Tokyo', featured: true } },
    ])).toEqual([]);
  });

  it('tolerates a missing or null bag', () => {
    expect(findUnknownKeys([
      { file: 'a.json' }, { file: 'b.json', type_metadata: null },
    ])).toEqual([]);
  });

  it('does not list a key as both consumed and unread', () => {
    const both = Object.keys(CONSUMED_KEYS).filter((k) => k in UNREAD_KEYS);
    expect(both, `listed twice: ${both.join(', ')}`).toEqual([]);
  });

  it('the whole corpus uses only registered keys', () => {
    const dir = path.join(process.cwd(), 'content', 'entries');
    const entries = fs.readdirSync(dir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => ({
        file: f,
        ...JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')),
      }));
    const unknown = findUnknownKeys(entries);
    const summary = [...new Set(unknown.map((u) => u.key))].join(', ');
    expect(unknown, `unregistered type_metadata key(s): ${summary}. Add it to ` +
      `src/lib/type-metadata-keys.ts with its consumer, or fix the typo.`).toEqual([]);
  });

  it('every registered key is actually in use somewhere', () => {
    // A registry that accumulates dead entries stops describing the system.
    const dir = path.join(process.cwd(), 'content', 'entries');
    const used = new Set<string>();
    for (const f of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8'));
      for (const k of Object.keys(d.type_metadata ?? {})) used.add(k);
    }
    const stale = [...KNOWN_KEYS].filter((k) => !used.has(k));
    expect(stale, `registered but used by no entry: ${stale.join(', ')}`).toEqual([]);
  });
});
