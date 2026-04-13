import {
  ENTRY_TYPES,
  SCANNER_SOURCES,
  type ValidationResult,
} from './schema';

const ID_PATTERN = /^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const ISO_DATETIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;
const URL_PATTERN = /^https?:\/\/.+/;
const MAX_SUMMARY_LENGTH = 1000;
const MAX_TITLE_LENGTH = 200;
const MAX_BLOCKQUOTE_LENGTH = 2000;

export function validateEntry(data: unknown): ValidationResult {
  const errors: string[] = [];

  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    return { valid: false, errors: ['Entry must be a non-null object'] };
  }

  const entry = data as Record<string, unknown>;

  // Required string fields
  const requiredStrings = [
    'id', 'date', 'type', 'title', 'summary',
    'blockquote', 'blockquote_source', 'source_url',
    'scanner_source', 'created_at',
  ] as const;

  for (const field of requiredStrings) {
    if (typeof entry[field] !== 'string' || entry[field] === '') {
      errors.push(`"${field}" must be a non-empty string`);
    }
  }

  // If basic string checks failed, return early
  if (errors.length > 0) {
    return { valid: false, errors };
  }

  const id = entry.id as string;
  const date = entry.date as string;
  const type = entry.type as string;
  const title = entry.title as string;
  const summary = entry.summary as string;
  const blockquote = entry.blockquote as string;
  const sourceUrl = entry.source_url as string;
  const scannerSource = entry.scanner_source as string;
  const createdAt = entry.created_at as string;

  // Format validations
  if (!ID_PATTERN.test(id)) {
    errors.push(`"id" must match YYYY-MM-DD-slug format, got "${id}"`);
  }

  if (!ISO_DATE_PATTERN.test(date)) {
    errors.push(`"date" must be ISO 8601 date (YYYY-MM-DD), got "${date}"`);
  } else {
    const parsed = new Date(date + 'T00:00:00Z');
    if (isNaN(parsed.getTime())) {
      errors.push(`"date" is not a valid date: "${date}"`);
    }
  }

  if (!ENTRY_TYPES.includes(type as any)) {
    errors.push(`"type" must be one of [${ENTRY_TYPES.join(', ')}], got "${type}"`);
  }

  if (!SCANNER_SOURCES.includes(scannerSource as any)) {
    errors.push(`"scanner_source" must be one of [${SCANNER_SOURCES.join(', ')}], got "${scannerSource}"`);
  }

  if (!URL_PATTERN.test(sourceUrl)) {
    errors.push(`"source_url" must be a valid HTTP(S) URL, got "${sourceUrl}"`);
  }

  if (!ISO_DATETIME_PATTERN.test(createdAt)) {
    errors.push(`"created_at" must be ISO 8601 datetime with Z suffix, got "${createdAt}"`);
  }

  // Length limits
  if (title.length > MAX_TITLE_LENGTH) {
    errors.push(`"title" exceeds ${MAX_TITLE_LENGTH} chars (got ${title.length})`);
  }

  if (summary.length > MAX_SUMMARY_LENGTH) {
    errors.push(`"summary" exceeds ${MAX_SUMMARY_LENGTH} chars (got ${summary.length})`);
  }

  if (blockquote.length > MAX_BLOCKQUOTE_LENGTH) {
    errors.push(`"blockquote" exceeds ${MAX_BLOCKQUOTE_LENGTH} chars (got ${blockquote.length})`);
  }

  // source_urls: optional array of {url, label} objects
  if (entry.source_urls !== undefined && entry.source_urls !== null) {
    if (!Array.isArray(entry.source_urls)) {
      errors.push(`"source_urls" must be an array or null`);
    } else {
      for (const item of entry.source_urls) {
        if (typeof item !== 'object' || item === null || typeof (item as any).url !== 'string' || typeof (item as any).label !== 'string') {
          errors.push(`"source_urls" items must have "url" and "label" strings`);
          break;
        }
      }
    }
  }

  // video_url: optional string
  if (entry.video_url !== undefined && entry.video_url !== null) {
    if (typeof entry.video_url !== 'string' || !URL_PATTERN.test(entry.video_url)) {
      errors.push(`"video_url" must be a valid HTTP(S) URL or null`);
    }
  }

  // Nullable string fields
  const nullableStrings = ['image', 'attribution', 'attribution_title', 'attribution_image'];
  for (const field of nullableStrings) {
    const val = entry[field];
    if (val !== null && typeof val !== 'string') {
      errors.push(`"${field}" must be a string or null`);
    }
  }

  // tags must be a non-empty array of strings
  if (!Array.isArray(entry.tags) || entry.tags.length === 0) {
    errors.push(`"tags" must be a non-empty array of strings`);
  } else if (!entry.tags.every((t: unknown) => typeof t === 'string' && t !== '')) {
    errors.push(`"tags" must contain only non-empty strings`);
  }

  // type_metadata must be an object
  if (typeof entry.type_metadata !== 'object' || entry.type_metadata === null || Array.isArray(entry.type_metadata)) {
    errors.push(`"type_metadata" must be an object`);
  }

  // verified must be boolean
  if (typeof entry.verified !== 'boolean') {
    errors.push(`"verified" must be a boolean`);
  }

  return { valid: errors.length === 0, errors };
}
