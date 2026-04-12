import { describe, it, expect } from 'vitest';
import { validateEntry } from '../src/lib/validate';

const validEntry = {
  id: '2026-04-10-long-now-event',
  date: '2026-04-10',
  type: 'event',
  title: 'Long Now Foundation',
  summary: 'Eric presents at Long Now on institutional design.',
  blockquote: 'Every institution you trust today was designed to be corruptible.',
  blockquote_source: 'Long Now Blog',
  source_url: 'https://longnow.org/events/incorruptible',
  image: null,
  attribution: null,
  attribution_title: null,
  attribution_image: null,
  tags: ['speaking', 'institutions'],
  type_metadata: {},
  scanner_source: 'web-search',
  verified: true,
  created_at: '2026-04-11T08:30:00Z',
};

describe('validateEntry', () => {
  it('accepts a valid entry', () => {
    const result = validateEntry(validEntry);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });
});
