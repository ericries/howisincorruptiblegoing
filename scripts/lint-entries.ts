import { validateEntry } from '../src/lib/validate';
import { scanEntry } from '../src/lib/injection';
import type { ValidationResult } from '../src/lib/schema';
import * as fs from 'fs';
import * as path from 'path';

// Read PNG/JPEG dimensions from file header without external deps.
function readImageDimensions(filePath: string): { width: number; height: number } | null {
  const buf = fs.readFileSync(filePath);
  // PNG: 8-byte signature, then IHDR width @ offset 16, height @ offset 20.
  if (
    buf.length >= 24 &&
    buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47
  ) {
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
  }
  // JPEG: scan for SOFn marker (0xFFC0..0xFFCF, excl. 0xC4/0xC8/0xCC).
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
    let i = 2;
    while (i + 8 < buf.length) {
      if (buf[i] !== 0xff) return null;
      const marker = buf[i + 1];
      const segLen = buf.readUInt16BE(i + 2);
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7) };
      }
      i += 2 + segLen;
    }
  }
  return null;
}

export function lintEntryFile(
  contents: string,
  filename: string,
): ValidationResult {
  const errors: string[] = [];

  // Parse JSON
  let data: unknown;
  try {
    data = JSON.parse(contents);
  } catch (e) {
    return { valid: false, errors: [`JSON parse error: ${(e as Error).message}`] };
  }

  // Schema validation
  const schemaResult = validateEntry(data);
  if (!schemaResult.valid) {
    errors.push(...schemaResult.errors);
  }

  // Injection detection
  if (typeof data === 'object' && data !== null) {
    const injectionResult = scanEntry(data as Record<string, unknown>);
    if (injectionResult.detected) {
      errors.push(...injectionResult.reasons.map((r) => `injection detected: ${r}`));
    }
  }

  // Filename must match id
  if (typeof data === 'object' && data !== null) {
    const entry = data as Record<string, unknown>;
    const expectedFilename = `${entry.id}.json`;
    if (filename !== expectedFilename) {
      errors.push(`filename "${filename}" does not match id "${entry.id}" (expected "${expectedFilename}")`);
    }
  }

  // Local image refs must exist on disk (under public/)
  if (typeof data === 'object' && data !== null) {
    const entry = data as Record<string, unknown>;
    for (const key of ['image', 'attribution_image']) {
      const val = entry[key];
      if (typeof val === 'string' && val.startsWith('/')) {
        const diskPath = path.join(process.cwd(), 'public', val);
        if (!fs.existsSync(diskPath)) {
          errors.push(`${key} "${val}" does not exist on disk at public${val}`);
        } else if (val.startsWith('/images/podcasts/')) {
          // Podcast covers render in the UpcomingStrip poster row at 1:1.
          // Wide/banner images blow up oversized; require near-square.
          const dims = readImageDimensions(diskPath);
          if (dims) {
            const ratio = dims.width / dims.height;
            if (ratio < 0.9 || ratio > 1.1) {
              errors.push(
                `${key} "${val}" is ${dims.width}x${dims.height} (aspect ${ratio.toFixed(2)}); ` +
                `podcast covers must be near-square (0.9–1.1) for the poster row. ` +
                `Use the iTunes Search API artworkUrl600 (always 600x600) instead of show-site banners.`,
              );
            }
          }
        }
      }
    }
  }

  return { valid: errors.length === 0, errors };
}

// CLI entrypoint: lint all JSON files in content/entries/
const isMainModule = process.argv[1]?.endsWith('lint-entries.ts');
if (isMainModule) {
  const entriesDir = path.join(process.cwd(), 'content', 'entries');

  if (!fs.existsSync(entriesDir)) {
    console.log('No content/entries/ directory found — nothing to lint.');
    process.exit(0);
  }

  const files = fs.readdirSync(entriesDir).filter((f) => f.endsWith('.json'));

  if (files.length === 0) {
    console.log('No entry files found — nothing to lint.');
    process.exit(0);
  }

  let hasErrors = false;

  for (const file of files) {
    const filePath = path.join(entriesDir, file);
    const contents = fs.readFileSync(filePath, 'utf-8');
    const result = lintEntryFile(contents, file);

    if (!result.valid) {
      hasErrors = true;
      console.error(`\n❌ ${file}:`);
      for (const error of result.errors) {
        console.error(`   - ${error}`);
      }
    } else {
      console.log(`✓ ${file}`);
    }
  }

  // Check endorsement adjacency — no two endorsements should be adjacent in sorted order
  const allEntries = files
    .map((f) => {
      const data = JSON.parse(fs.readFileSync(path.join(entriesDir, f), 'utf-8'));
      return { file: f, type: data.type, date: data.date, id: data.id, parent_id: data.parent_id ?? null };
    })
    .sort((a, b) => {
      // Sort by date, then by filename for same-date entries
      const dateCompare = a.date.localeCompare(b.date);
      if (dateCompare !== 0) return dateCompare;
      return a.file.localeCompare(b.file);
    });

  // Reaction parent_id must resolve to a non-reaction entry (no nesting, no orphans)
  const idToEntry = new Map(allEntries.map((e) => [e.id, e]));
  for (const e of allEntries) {
    if (e.type !== 'reaction') continue;
    if (!e.parent_id) continue; // validateEntry already caught this
    const parent = idToEntry.get(e.parent_id);
    if (!parent) {
      hasErrors = true;
      console.error(`\n❌ ORPHAN REACTION: ${e.file} parent_id "${e.parent_id}" does not resolve to any entry`);
    } else if (parent.type === 'reaction') {
      hasErrors = true;
      console.error(`\n❌ NESTED REACTION: ${e.file} parent_id "${e.parent_id}" is itself a reaction; reactions cannot nest`);
    }
  }

  // Highlights row floor — the carousel is meant to GROW over time, not be
  // pruned. The floor is the count of type_metadata.highlight entries we
  // currently honor. Any commit that drops the count below the floor fails
  // lint. Raise the floor whenever a new highlight is legitimately added
  // (do not lower it). See memory/feedback_highlights_row_grows.md and the
  // 2026-06-04 chat: "the top rows of highlights are meant to get longer
  // and longer, not be pruned".
  const HIGHLIGHTS_FLOOR = 16;
  let highlightsCount = 0;
  for (const f of files) {
    const data = JSON.parse(fs.readFileSync(path.join(entriesDir, f), 'utf-8'));
    if (data.type_metadata?.highlight) highlightsCount++;
  }
  if (highlightsCount < HIGHLIGHTS_FLOOR) {
    hasErrors = true;
    console.error(
      `\n❌ HIGHLIGHTS FLOOR: only ${highlightsCount} entries have type_metadata.highlight, ` +
      `floor is ${HIGHLIGHTS_FLOOR}. The carousel grows; it does not shrink. ` +
      `Restore missing highlight flags or, if a highlight was legitimately removed ` +
      `(e.g. the entry was deleted), lower the floor in scripts/lint-entries.ts.`,
    );
  }

  let lastEndorsementIndex = -999;
  for (let i = 0; i < allEntries.length; i++) {
    const entry = allEntries[i];
    const isEndorsement = entry.type === 'endorsement' && entry.file.includes('-endorsement-');
    if (isEndorsement) {
      const gap = i - lastEndorsementIndex - 1;
      if (gap < 2 && lastEndorsementIndex >= 0) {
        hasErrors = true;
        const prevEndorsement = allEntries[lastEndorsementIndex];
        console.error(`\n❌ ADJACENCY: ${entry.file} is only ${gap} entries after ${prevEndorsement.file} (need at least 2 non-endorsement entries between endorsements)`);
      }
      lastEndorsementIndex = i;
    }
  }

  process.exit(hasErrors ? 1 : 0);
}
