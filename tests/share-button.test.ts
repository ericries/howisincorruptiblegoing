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

describe('ShareButton source — platform-gated native share (Lesson A)', () => {
  it('detects Apple platforms (iOS, iPadOS, macOS) for native share', () => {
    // macOS desktop (including Chrome → macOS Sharing widget) is a yes;
    // iOS/iPadOS are yes via the same Apple check or the touch fallback.
    expect(SHARE_SRC).toMatch(/Mac\|iPhone\|iPad/);
  });

  it('detects Android for native share', () => {
    // Chrome's share sheet on Android is the canonical pattern.
    expect(SHARE_SRC).toMatch(/Android/);
  });

  it('also accepts other touch devices (fallback)', () => {
    // Any device whose primary pointer is coarse / has touch points gets
    // the native sheet too, so we don't miss e.g. Surface tablets.
    expect(SHARE_SRC).toMatch(/maxTouchPoints\s*>\s*0/);
    expect(SHARE_SRC).toMatch(/pointer:\s*coarse/);
  });

  it('does NOT trigger native share on Windows / Linux desktop', () => {
    // The gating logic must NOT match Windows or Linux as positive platforms.
    // Those get the popover instead, because their native share UI is uneven.
    const block = SHARE_SRC.match(/const\s+canNativeShare\s*=[\s\S]{0,300}/);
    expect(block, 'canNativeShare definition not found').not.toBeNull();
    expect(block![0]).not.toMatch(/Win|Linux/);
  });

  it('requires navigator.share to be a function (capability check)', () => {
    expect(SHARE_SRC).toMatch(/typeof\s+\(navigator\s+as\s+any\)\.share\s*===\s*['"]function['"]/);
  });

  it('does NOT probe canShare with an empty Blob (iOS Safari rejects it — 2026-06-08 postmortem)', () => {
    // The first-pass code used `canShare({ files: [new File([new Blob()], …)] })`
    // as a feature probe. iOS Safari validates file contents and returned
    // false on the very devices where native share was supposed to work,
    // so the click handler fell through to the desktop popover. The fix is
    // to drop the upfront probe and let nativeShare() attempt the file
    // share directly. If anyone reintroduces the empty-Blob probe, this
    // test catches it.
    expect(SHARE_SRC).not.toMatch(/new File\(\s*\[\s*new Blob\(\s*\)\s*\]/);
  });

  it('does NOT gate the file share on canShare (Chrome/macOS lies — 2026-06-08 follow-up)', () => {
    // After the iOS fix, Chrome on macOS was still URL-only. Root cause:
    // canShare({ files: [pngFile] }) returns false on Chrome desktop even
    // when navigator.share({ files }) would actually succeed. Trust the
    // attempt, not the prediction — try the file share and catch the
    // rejection. This test fails if someone re-adds a canShare gate around
    // the navigator.share({ files }) call.
    const nativeShareSrc = SHARE_SRC.slice(
      SHARE_SRC.indexOf('async function nativeShare'),
      SHARE_SRC.indexOf('function tooltip'),
    );
    expect(nativeShareSrc.length, 'expected nativeShare body extract').toBeGreaterThan(100);
    expect(
      nativeShareSrc,
      'no upfront canShare check should sit between the File construction and navigator.share({files})',
    ).not.toMatch(/canShare\([^)]*files[^)]*\)\s*\)?\s*\{/);
  });

  it('falls back to URL-only share when the file path fails', () => {
    // The click handler must still gracefully handle the case where the
    // platform rejects the file share or fetch fails. The source must
    // contain BOTH a file-attached share AND a URL-only share so users
    // always get the OS sheet — even if the file attach didn't work out.
    expect(SHARE_SRC).toMatch(/navigator\.share\(\s*\{\s*files:\s*\[\s*file\s*\]/);
    expect(SHARE_SRC).toMatch(/navigator\.share\(\s*\{\s*url\s*,\s*title\s*,\s*text\s*\}\s*\)/);
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

describe('ShareButton source — popover platform set (user direction 2026-06-08)', () => {
  it('offers LinkedIn and Bluesky in the popover', () => {
    expect(SHARE_SRC).toMatch(/data-menu-action="linkedin"/);
    expect(SHARE_SRC).toMatch(/data-menu-action="bluesky"/);
    // Their intent URLs must be the canonical web-share endpoints.
    expect(SHARE_SRC).toMatch(/linkedin\.com\/sharing\/share-offsite/);
    expect(SHARE_SRC).toMatch(/bsky\.app\/intent\/compose/);
  });

  it('does NOT offer X / Twitter (user direction)', () => {
    // Per the 2026-06-08 direction, drop X from the popover. Mobile / macOS
    // users still get X in the native sheet if they have the app installed.
    expect(SHARE_SRC).not.toMatch(/twitter\.com\/intent/);
    expect(SHARE_SRC).not.toMatch(/data-menu-action="x"/);
    expect(SHARE_SRC).not.toMatch(/Share on X/);
  });

  it('does NOT offer Instagram / YouTube / TikTok in the popover (no web intent URLs)', () => {
    // These platforms don't expose web-share intent endpoints; sharing to
    // them happens through the native sheet on mobile / macOS. Adding
    // placeholder menu items would be misleading.
    expect(SHARE_SRC).not.toMatch(/data-menu-action="instagram"/);
    expect(SHARE_SRC).not.toMatch(/data-menu-action="youtube"/);
    expect(SHARE_SRC).not.toMatch(/data-menu-action="tiktok"/);
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
              <a data-menu-action="linkedin" href="#"></a>
              <a data-menu-action="bluesky" href="#"></a>
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
