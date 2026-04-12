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

describe('validateEntry rejects invalid entries', () => {
  // Helper: clone valid entry and override fields
  function entryWith(overrides: Record<string, unknown>) {
    return { ...validEntry, ...overrides };
  }

  it('rejects non-object input', () => {
    expect(validateEntry('string')).toEqual({
      valid: false,
      errors: ['Entry must be a non-null object'],
    });
    expect(validateEntry(null)).toEqual({
      valid: false,
      errors: ['Entry must be a non-null object'],
    });
    expect(validateEntry([1, 2])).toEqual({
      valid: false,
      errors: ['Entry must be a non-null object'],
    });
  });

  it('rejects missing required string fields', () => {
    const result = validateEntry({});
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0]).toContain('must be a non-empty string');
  });

  it('rejects empty string for required fields', () => {
    const result = validateEntry(entryWith({ title: '' }));
    expect(result.valid).toBe(false);
    expect(result.errors).toContain('"title" must be a non-empty string');
  });

  it('rejects invalid id format', () => {
    const result = validateEntry(entryWith({ id: 'bad-id' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"id" must match YYYY-MM-DD-slug format');
  });

  it('rejects invalid date format', () => {
    const result = validateEntry(entryWith({ date: '04-10-2026' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"date" must be ISO 8601 date');
  });

  it('rejects invalid date value', () => {
    const result = validateEntry(entryWith({ date: '2026-13-45' }));
    expect(result.valid).toBe(false);
  });

  it('rejects invalid type enum', () => {
    const result = validateEntry(entryWith({ type: 'blog' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"type" must be one of');
  });

  it('rejects invalid scanner_source', () => {
    const result = validateEntry(entryWith({ scanner_source: 'crawl' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"scanner_source" must be one of');
  });

  it('rejects invalid source_url', () => {
    const result = validateEntry(entryWith({ source_url: 'not-a-url' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"source_url" must be a valid HTTP(S) URL');
  });

  it('rejects invalid created_at format', () => {
    const result = validateEntry(entryWith({ created_at: '2026-04-11' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"created_at" must be ISO 8601 datetime');
  });

  it('rejects title exceeding max length', () => {
    const result = validateEntry(entryWith({ title: 'x'.repeat(201) }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"title" exceeds');
  });

  it('rejects summary exceeding max length', () => {
    const result = validateEntry(entryWith({ summary: 'x'.repeat(501) }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"summary" exceeds');
  });

  it('rejects blockquote exceeding max length', () => {
    const result = validateEntry(entryWith({ blockquote: 'x'.repeat(1001) }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"blockquote" exceeds');
  });

  it('rejects non-null non-string for nullable fields', () => {
    const result = validateEntry(entryWith({ image: 123 }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"image" must be a string or null');
  });

  it('rejects empty tags array', () => {
    const result = validateEntry(entryWith({ tags: [] }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"tags" must be a non-empty array');
  });

  it('rejects non-string tags', () => {
    const result = validateEntry(entryWith({ tags: [123] }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"tags" must contain only non-empty strings');
  });

  it('rejects non-object type_metadata', () => {
    const result = validateEntry(entryWith({ type_metadata: 'string' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"type_metadata" must be an object');
  });

  it('rejects non-boolean verified', () => {
    const result = validateEntry(entryWith({ verified: 'yes' }));
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('"verified" must be a boolean');
  });

  it('collects multiple errors', () => {
    const result = validateEntry(entryWith({
      id: 'bad',
      type: 'invalid',
      source_url: 'nope',
    }));
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(3);
  });
});
