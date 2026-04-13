export const ENTRY_TYPES = [
  'event',
  'endorsement',
  'review',
  'social',
  'podcast',
  'media',
  'milestone',
] as const;

export type EntryType = (typeof ENTRY_TYPES)[number];

export const SCANNER_SOURCES = [
  'web-search',
  'social-scan',
  'manual',
  'rss',
] as const;

export type ScannerSource = (typeof SCANNER_SOURCES)[number];

export interface TimelineEntry {
  id: string;
  date: string;
  type: EntryType;
  title: string;
  summary: string;
  blockquote: string;
  blockquote_source: string;
  source_url: string;
  source_urls: { url: string; label: string }[] | null;
  video_url: string | null;
  image: string | null;
  attribution: string | null;
  attribution_title: string | null;
  attribution_image: string | null;
  tags: string[];
  type_metadata: Record<string, unknown>;
  scanner_source: ScannerSource;
  verified: boolean;
  created_at: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}
