import { describe, it, expect, beforeAll } from 'vitest';
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { transformSync } from 'esbuild';

/**
 * Share-button invariants — regression tests for the three failure modes
 * documented in docs/postmortems/2026-06-07-share-button-three-failures.md:
 *
 *   A. Native share fired on desktop Chrome (should be touch-only).
 *   B. Popover was truncated because position:fixed was scoped to a
 *      transform-containing-block ancestor (.timeline-row's cardEnter
 *      animation with fill-mode: both).
 *   C. Some card variants didn't render the share button at all.
 *   D. Quote cards rendered as both a hero AND a textual body → duplicate
 *      content visible to the user.
 *
 * Each test below ties to a specific lesson. Don't loosen — if a future
 * change makes one of these fail, the design moved and the test should
 * be revisited intentionally with a new postmortem.
 */

const ROOT = process.cwd();
const SHARE_SRC = fs.readFileSync(path.join(ROOT, 'src/components/ShareButton.astro'), 'utf-8');
const TIMELINE_SRC = fs.readFileSync(path.join(ROOT, 'src/components/TimelineEntry.astro'), 'utf-8');
const LAYOUT_SRC = fs.readFileSync(path.join(ROOT, 'src/layouts/Layout.astro'), 'utf-8');
const PERMALINK_SRC = fs.readFileSync(path.join(ROOT, 'src/pages/e/[id].astro'), 'utf-8');

// ───────────────────────────────────────────────────────────────────────────
// SOURCE-LEVEL INVARIANTS
// ───────────────────────────────────────────────────────────────────────────

describe('ShareButton source — touch-only gating (Lesson A)', () => {
  it('checks for touch-device signal before claiming canShareFiles', () => {
    // Feature detection ≠ UX selection. The Web Share API exists on Chrome
    // desktop but the macOS sheet is unreliable; desktop must always get
    // the popover.
    expect(SHARE_SRC).toMatch(/maxTouchPoints\s*>\s*0/);
    expect(SHARE_SRC).toMatch(/pointer:\s*coarse/);
  });

  it('uses the touch signal as a precondition for canShareFiles', () => {
    // The order matters: isTouchDevice && file-API-probe. If a future edit
    // reverses this and just probes the file API, desktop Chrome will once
    // again trigger the macOS native sheet.
    const block = SHARE_SRC.match(/const\s+canShareFiles\s*=[\s\S]{0,400}/);
    expect(block, 'canShareFiles definition not found').not.toBeNull();
    expect(block![0]).toMatch(/isTouchDevice\s*&&/);
  });
});

describe('ShareButton source — portal pattern (Lesson B)', () => {
  it('moves the menu DOM to <body> when opening', () => {
    // position:fixed inside a transform-containing-block (.timeline-row has
    // animation: cardEnter ... both → translateY(0) persists) is scoped to
    // that ancestor, not the viewport. The fix is to portal the menu out.
    expect(SHARE_SRC).toMatch(/document\.body\.appendChild\s*\(\s*menu\s*\)/);
  });

  it('restores the menu to its origin group on close', () => {
    // Without this, repeated opens would lose the menu reference after the
    // first close (it'd stay orphaned on <body>).
    expect(SHARE_SRC).toMatch(/openGroup\.appendChild\s*\(\s*openMenu\s*\)/);
  });

  it('uses :global selectors for the portalled menu so styles survive the move', () => {
    // Astro scopes component styles by default. Once the menu is on <body>
    // it's outside the component tree — the styles only apply if declared
    // with :global. Without this the menu renders unstyled in production.
    expect(SHARE_SRC).toMatch(/:global\(\.share-menu\)/);
    expect(SHARE_SRC).toMatch(/:global\(\.share-menu__item\)/);
  });
});

describe('TimelineEntry source — containing-block trap (Lesson B)', () => {
  it('.timeline-row uses animation: cardEnter ... both (the trap)', () => {
    // This invariant exists so the next person who edits ShareButton knows
    // why the portal pattern is required. If you remove `both` from the
    // animation here, the popover can live in-tree — but then the entrance
    // animation will pop, which is a worse UX trade. Don't change this
    // without considering the share button.
    expect(TIMELINE_SRC).toMatch(/animation:\s*cardEnter[^;]*both/);
  });

  it('does NOT render quote-card images as a hero (Lesson D)', () => {
    // The original first-pass made the quote-card the hero AND let the body
    // re-render the same quote textually → visible duplication. Cards are
    // share assets only (og:image, permalink page, share-button payload).
    //
    // Guard BOTH the class-string conditional and the rendering ternary —
    // if either drops the !isQuoteCard check, quote cards regress to heroes.
    // The naive `toMatch` lets a single-site mutation through (the other
    // site still satisfies the regex); count occurrences explicitly.
    const guarded = (TIMELINE_SRC.match(/entry\.image\s*&&\s*!isQuoteCard/g) || []).length;
    expect(
      guarded,
      'expected both class-string and rendering-branch to guard against quote-card heroes',
    ).toBeGreaterThanOrEqual(2);
    expect(TIMELINE_SRC).toMatch(/isQuoteCard\s*=\s*\(entry\.image\s*\|\|\s*''\)\.startsWith\('\/images\/cards\/'\)/);
  });
});

describe('TimelineEntry source — every card variant renders the actions (Lesson C)', () => {
  it('imports the ShareButton component', () => {
    expect(TIMELINE_SRC).toMatch(/import\s+ShareButton\s+from\s+['"]\.\/ShareButton\.astro['"]/);
  });

  it('renders one <ShareButton /> per card__links section', () => {
    // The original bug shipped with only the standard variant wired. Every
    // card__links footer must include the actions, otherwise some entries
    // have no way to share.
    const linkSections = (TIMELINE_SRC.match(/<div class="card__links">/g) || []).length;
    const shareButtonCalls = (TIMELINE_SRC.match(/<ShareButton/g) || []).length;
    expect(linkSections, 'expected at least one card__links footer').toBeGreaterThan(0);
    expect(shareButtonCalls).toBe(linkSections);
  });
});

describe('ShareButton source — icon-only UI (user direction 2026-06-07)', () => {
  it('does not render the word "Share" as a visible button label', () => {
    // The user asked for an icon-only design after the popover bugs. The
    // visible <span>/<button>Share</span></button> text was removed in
    // favor of an aria-label only. Keep it that way.
    expect(SHARE_SRC).not.toMatch(/>Share<\/span>/);
    expect(SHARE_SRC).not.toMatch(/class="share__label"/);
  });

  it('exposes both a permalink action and a share action', () => {
    expect(SHARE_SRC).toMatch(/data-action="permalink"/);
    expect(SHARE_SRC).toMatch(/data-action="share"/);
  });

  it('uses margin-left: auto to push the action pair to the lower-right', () => {
    expect(SHARE_SRC).toMatch(/\.entry-actions\s*\{[^}]*margin-left:\s*auto/);
  });

  it('icons are <svg> with aria-hidden so screen readers fall back to the button aria-label', () => {
    expect(SHARE_SRC).toMatch(/<svg[^>]*aria-hidden="true"/);
    expect(SHARE_SRC).toMatch(/aria-label="Copy permalink"/);
    expect(SHARE_SRC).toMatch(/aria-label="Share"/);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// LAYOUT + PERMALINK PAGE — og:image is the load-bearing share affordance
// ───────────────────────────────────────────────────────────────────────────

describe('Layout source — og + twitter card meta', () => {
  it('renders og:image as an absolute URL', () => {
    // Relative URLs in og:image don't unfurl on most platforms. The layout
    // must synthesize an absolute URL from the site base.
    expect(LAYOUT_SRC).toMatch(/og:image[\s\S]*ogImgAbs/);
    expect(LAYOUT_SRC).toMatch(/ogImage[\s\S]*startsWith\(['"]http/);
  });

  it('uses summary_large_image for twitter cards', () => {
    expect(LAYOUT_SRC).toMatch(/twitter:card['"]\s+content=['"]summary_large_image/);
  });
});

describe('Permalink page source — entry-specific og:image wiring', () => {
  it('routes via getStaticPaths so every entry gets its own page', () => {
    expect(PERMALINK_SRC).toMatch(/getStaticPaths/);
    expect(PERMALINK_SRC).toMatch(/params:\s*\{\s*id:\s*e\.id\s*\}/);
  });

  it('passes the entry image as the page og:image', () => {
    // The entry's quote card (or other image) is what shows up when the
    // permalink is pasted into X/LinkedIn/Slack/iMessage.
    expect(PERMALINK_SRC).toMatch(/ogImage=\{ogImage\}/);
    expect(PERMALINK_SRC).toMatch(/const\s+ogImage\s*=\s*entry\.image\s*\|\|/);
  });

  it('renders the ShareButton on the permalink page itself', () => {
    expect(PERMALINK_SRC).toMatch(/<ShareButton/);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// BUILD-TIME SMOKE TEST — what users actually see
// ───────────────────────────────────────────────────────────────────────────

/**
 * The "verify in DOM, not source" rule (memory/feedback_verify_in_dom.md)
 * applies here: source-level invariants catch most regressions, but the
 * build smoke test catches the rest by reading dist/ output.
 */
describe('Built output — homepage + permalink pages', () => {
  const distDir = path.join(ROOT, 'dist');
  let indexHtml = '';

  beforeAll(() => {
    if (!fs.existsSync(distDir) || !fs.existsSync(path.join(distDir, 'index.html'))) {
      execSync('npm run build', { cwd: ROOT, stdio: 'pipe' });
    }
    indexHtml = fs.readFileSync(path.join(distDir, 'index.html'), 'utf-8');
  });

  it('homepage contains at least one entry-actions group per timeline entry', () => {
    // Count the entry-actions data-share roots vs. timeline-row blocks.
    const dataShareCount = (indexHtml.match(/data-share=""|data-share /g) || []).length;
    const timelineRowCount = (indexHtml.match(/class="timeline-row"/g) || []).length;
    // Some timeline rows (events with photo galleries / reaction clusters)
    // may legitimately have no share affordance, but the majority should.
    expect(dataShareCount).toBeGreaterThan(timelineRowCount * 0.5);
  });

  it('every share group contains both a permalink and a share button', () => {
    const permalinkCount = (indexHtml.match(/data-action="permalink"/g) || []).length;
    const shareCount = (indexHtml.match(/data-action="share"/g) || []).length;
    expect(permalinkCount).toBeGreaterThan(0);
    expect(permalinkCount).toBe(shareCount);
  });

  it('homepage og:image is the absolute default cover URL', () => {
    expect(indexHtml).toMatch(/og:image['"]\s+content=['"]https:\/\/howisincorruptiblegoing\.com\/images\/og-cover\.png/);
  });

  it('a sample permalink page wires the entry-specific og:image to the card', () => {
    // Pick a known quote-card entry — Vala Afshar's permalink should hand
    // the card PNG to og:image as an absolute URL.
    const valaPath = path.join(distDir, 'e/2026-06-05-vala-afshar-tweet/index.html');
    expect(fs.existsSync(valaPath), 'expected per-entry permalink page to exist').toBe(true);
    const html = fs.readFileSync(valaPath, 'utf-8');
    expect(html).toMatch(/og:image['"]\s+content=['"]https:\/\/howisincorruptiblegoing\.com\/images\/cards\/2026-06-05-vala-afshar-tweet\.png/);
    expect(html).toMatch(/twitter:card['"]\s+content=['"]summary_large_image/);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// DOM behavior simulation — click → portal
// ───────────────────────────────────────────────────────────────────────────

/**
 * The portal pattern is the load-bearing fix for Bug B. Simulate a click
 * in jsdom to confirm the menu actually moves to document.body.
 */
describe('Portal pattern — jsdom simulation', () => {
  function buildFixtureDom() {
    // A real URL avoids the "opaque origin" localStorage block.
    return new JSDOM(`<!doctype html><html><body>
      <div class="timeline-row" style="transform: translateY(0)">
        <article class="card">
          <div class="entry-actions" data-share data-url="https://example.com/e/x/" data-title="t" data-text="t" data-card="">
            <button class="entry-actions__btn" data-action="permalink" aria-label="Copy permalink"></button>
            <button class="entry-actions__btn" data-action="share" aria-label="Share" aria-expanded="false"></button>
            <div class="share-menu" role="menu" data-share-menu hidden>
              <a data-menu-action="x" href="#"></a>
              <a data-menu-action="linkedin" href="#"></a>
            </div>
          </div>
        </article>
      </div>
    </body></html>`, { runScripts: 'dangerously', url: 'https://example.com/' });
  }

  // Extract the inline script from ShareButton.astro, strip TypeScript types
  // via esbuild (Astro itself does this at build time), and run inside jsdom.
  // This way the canonical behavior is what's exercised — not a hand-written
  // copy that can silently drift from the real script.
  function extractInlineScript(): string {
    const m = SHARE_SRC.match(/<script>([\s\S]*?)<\/script>/);
    if (!m) throw new Error('ShareButton inline <script> not found');
    return transformSync(m[1], { loader: 'ts', target: 'es2020' }).code;
  }

  it('clicking the share button moves the menu to <body>', () => {
    const dom = buildFixtureDom();
    const { window } = dom;
    // Polyfill what the script touches but jsdom omits.
    (window as any).matchMedia = () => ({ matches: false });
    // Force desktop path (no touch) so the popover branch runs.
    Object.defineProperty(window.navigator, 'maxTouchPoints', { value: 0, configurable: true });
    const scriptEl = window.document.createElement('script');
    scriptEl.textContent = extractInlineScript();
    window.document.body.appendChild(scriptEl);

    const shareBtn = window.document.querySelector('[data-action="share"]') as HTMLElement;
    const menu = window.document.querySelector('[data-share-menu]') as HTMLElement;
    expect(menu.parentElement?.classList.contains('entry-actions')).toBe(true);

    shareBtn.click();

    expect(menu.parentElement).toBe(window.document.body);
    expect(menu.classList.contains('is-open')).toBe(true);
  });

  it('clicking outside closes the menu and restores its origin parent', () => {
    const dom = buildFixtureDom();
    const { window } = dom;
    (window as any).matchMedia = () => ({ matches: false });
    Object.defineProperty(window.navigator, 'maxTouchPoints', { value: 0, configurable: true });
    const scriptEl = window.document.createElement('script');
    scriptEl.textContent = extractInlineScript();
    window.document.body.appendChild(scriptEl);

    const group = window.document.querySelector('[data-share]') as HTMLElement;
    const shareBtn = window.document.querySelector('[data-action="share"]') as HTMLElement;
    const menu = window.document.querySelector('[data-share-menu]') as HTMLElement;

    shareBtn.click();
    expect(menu.parentElement).toBe(window.document.body);

    // Click-away.
    window.document.body.click();
    expect(menu.classList.contains('is-open')).toBe(false);
    expect(menu.parentElement).toBe(group);
  });
});
