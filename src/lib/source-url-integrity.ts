/**
 * Guards against two source_url failure modes, both observed in October 2026.
 *
 * 1. Fabricated citations. On 2026-10-16 an entry was written in a batch with
 *    ".../activity-7515320000000000000-xxxx" standing in for a URL that was not
 *    to hand. It was spotted by eye before commit, but nothing in the pipeline
 *    would have stopped it, and a false citation is indistinguishable from a
 *    real one once it ships. CLAUDE.md's rule — never create an entry you
 *    cannot source — needs an enforcement point, not just a reminder.
 *
 * 2. Silent duplicates. Three entries were built on
 *    thoughteconomics.com/eric-ries/, two of them near-identical, and nobody
 *    noticed for five days. scan-triage.py dedupes within a single dataset; it
 *    cannot see an entry created by a different cycle on a different day.
 */

/** URLs legitimately shared across many entries — never duplicate warnings. */
export const SHARED_CANONICAL_URLS: readonly string[] = [
  'https://incorruptible.co',
  'https://www.incorruptible.co',
  'https://www.amazon.com/Incorruptible-Good-Companies-Great-Stay/product-reviews/B0FWZZBPZB',
  'https://www.amazon.com/Incorruptible-Good-Companies-Great-Stay/dp/B0FWZZBPZB',
];

const PLACEHOLDER_TOKENS = [
  'xxxx', 'yyyy', 'zzzz', 'placeholder', 'example.com', 'example.org',
  'todo', 'tbd', 'fixme', 'lorem',
];

/**
 * True when a URL looks invented rather than observed.
 *
 * Deliberately conservative: a false positive costs one manual confirmation,
 * a false negative ships a fake citation.
 */
export function looksFabricated(url: string): boolean {
  if (!url) return false;
  const lower = url.toLowerCase();

  for (const tok of PLACEHOLDER_TOKENS) {
    if (lower.includes(tok)) return true;
  }

  // LinkedIn activity ids are 19 densely-varied digits. A run of 8+ trailing
  // zeros is not something the platform mints — it is a human padding a gap.
  const activity = lower.match(/activity[-:](\d{6,})/);
  if (activity && /0{8,}$/.test(activity[1])) return true;

  // Same reasoning for X status ids.
  const status = lower.match(/status\/(\d{6,})/);
  if (status && /0{8,}$/.test(status[1])) return true;

  return false;
}

export interface DuplicateGroup {
  url: string;
  files: string[];
}

/**
 * Entries sharing a source_url, excluding the canonical book/Amazon pages.
 *
 * Shared sources are not always wrong — an event entry and a reaction can
 * legitimately cite the same post — so callers should treat this as a warning
 * to review, not an automatic failure.
 */
export function findDuplicateSourceUrls(
  entries: Array<{ file: string; source_url?: string | null }>
): DuplicateGroup[] {
  const shared = new Set(SHARED_CANONICAL_URLS.map((u) => u.replace(/\/+$/, '')));
  // Group on a trailing-slash-insensitive key, but report the URL as written so
  // the warning can be pasted straight into a browser.
  const byUrl = new Map<string, { display: string; files: string[] }>();

  for (const e of entries) {
    const raw = (e.source_url || '').trim();
    if (!raw) continue;
    const key = raw.replace(/\/+$/, '');
    if (shared.has(key)) continue;
    const group = byUrl.get(key) || { display: raw, files: [] };
    group.files.push(e.file);
    byUrl.set(key, group);
  }

  const out: DuplicateGroup[] = [];
  for (const { display, files } of byUrl.values()) {
    if (files.length > 1) out.push({ url: display, files });
  }
  return out.sort((a, b) => b.files.length - a.files.length);
}
