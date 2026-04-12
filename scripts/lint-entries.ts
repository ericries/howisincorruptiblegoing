import { validateEntry } from '../src/lib/validate';
import { scanEntry } from '../src/lib/injection';
import type { ValidationResult } from '../src/lib/schema';
import * as fs from 'fs';
import * as path from 'path';

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

  process.exit(hasErrors ? 1 : 0);
}
