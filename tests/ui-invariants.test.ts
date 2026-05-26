import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * UI invariant regression tests.
 *
 * These exist because I've broken the UpcomingStrip layout twice (skinny
 * cards, oversized HBR) by changing CSS without verifying the resulting
 * shape matches what the row of cards needs. The tests parse the source
 * .astro file and assert that the load-bearing CSS rules and ordering
 * arrays still hold their invariants. Edit the constants in the test
 * file when the design itself changes — don't loosen the assertions to
 * silence a regression.
 */

const stripPath = path.join(process.cwd(), 'src/components/UpcomingStrip.astro');
const stripSource = fs.readFileSync(stripPath, 'utf-8');

function ruleFor(selector: string): string {
  const re = new RegExp(`${selector.replace('.', '\\.')}\\s*\\{[^}]+\\}`);
  const m = stripSource.match(re);
  if (!m) throw new Error(`CSS rule for ${selector} not found in UpcomingStrip.astro`);
  return m[0];
}

describe('UpcomingStrip poster-card CSS', () => {
  it('poster-card__art is 16:9 (not 1:1 — that makes the cards skinny)', () => {
    expect(ruleFor('.poster-card__art')).toMatch(/aspect-ratio:\s*16\s*\/\s*9/);
  });

  it('poster-card pins both flex-basis and max-width to 192px', () => {
    const rule = ruleFor('.poster-card');
    // Both bounds are required: flex-basis alone is overridden by an image's
    // intrinsic width because flex items default to min-width:auto.
    expect(rule).toMatch(/flex:\s*0\s+0\s+192px/);
    expect(rule).toMatch(/max-width:\s*192px/);
    expect(rule).toMatch(/min-width:\s*0/);
  });

  it('square iTunes covers letterbox (object-fit:contain) instead of cover', () => {
    // Without this, 600x600 podcast covers center-crop in a 16:9 frame and
    // lose the show title at top/bottom.
    expect(stripSource).toMatch(
      /\.poster-card__img\[data-image-mode="contain"\][^}]*object-fit:\s*contain/,
    );
  });

  it('poster-card img wires data-image-mode from the PosterCard', () => {
    // Pair the CSS above with the JSX: the data attr must actually be
    // rendered, otherwise the contain rule never matches.
    expect(stripSource).toMatch(/data-image-mode=\{p\.imageMode\}/);
  });
});

describe('UpcomingStrip quoteCards ordering', () => {
  function extractIds(varName: string): string[] {
    const idx = stripSource.indexOf(`const ${varName}`);
    if (idx === -1) throw new Error(`${varName} not found`);
    // Stop at the closing `];` of the array literal.
    const end = stripSource.indexOf('];', idx);
    const block = stripSource.slice(idx, end);
    return [...block.matchAll(/'(2026-[\w-]+)'/g)].map((m) => m[1]);
  }

  it('row of faces starts with Frei, then Grant, then Heath', () => {
    const front = extractIds('QUOTE_FRONT_ORDER');
    expect(front[0]).toBe('2026-05-16-frances-frei-incorruptible-comment');
    expect(front[1]).toBe('2026-05-02-endorsement-adam-grant');
    expect(front[2]).toBe('2026-04-21-dan-heath-best-business-book');
  });

  it('Nir Eyal is in the tail (not the front)', () => {
    const front = extractIds('QUOTE_FRONT_ORDER');
    const tail = extractIds('QUOTE_TAIL_ORDER');
    const eyalId = '2026-05-26-nir-eyal-launch-day-tweet';
    expect(front, 'Eyal must not be pinned to the front').not.toContain(eyalId);
    expect(tail, 'Eyal must be pinned to the tail').toContain(eyalId);
  });

  it('Tim O\'Reilly remains pinned last in the tail', () => {
    const tail = extractIds('QUOTE_TAIL_ORDER');
    expect(tail[tail.length - 1]).toBe('2026-02-27-endorsement-tim-oreilly');
  });
});

describe('UpcomingStrip posterCards ordering', () => {
  function extractIds(varName: string): string[] {
    const idx = stripSource.indexOf(`const ${varName}`);
    if (idx === -1) throw new Error(`${varName} not found`);
    const end = stripSource.indexOf('];', idx);
    const block = stripSource.slice(idx, end);
    return [...block.matchAll(/'(2026-[\w-]+)'/g)].map((m) => m[1]);
  }

  it('podcast row starts with Lenny then YC then Ageless then HBR', () => {
    const pins = extractIds('POSTER_PINS');
    expect(pins[0]).toBe('2026-05-10-lennys-podcast-rachitsky');
    expect(pins[1]).toBe('2026-05-22-yc-main-function-garry-tan');
    expect(pins[2]).toBe('2026-04-07-david-meyer-ageless-warrior');
    expect(pins[3]).toBe('2026-05-26-hbr-ideacast-sophisticated-zombies');
  });
});
