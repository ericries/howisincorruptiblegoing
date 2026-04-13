# How Is Incorruptible Going?

Timeline website tracking momentum for Eric Ries's book *Incorruptible* (May 26, 2026).

## Environment

- **Node.js:** Requires >=22.12 (Astro 6). Use `/opt/homebrew/opt/node@23/bin` — set `export PATH="/opt/homebrew/opt/node@23/bin:$PATH"` before running npm/npx commands. System default node (v18) is too old.

## Project Overview

- **Spec:** `docs/superpowers/specs/2026-04-12-incorruptible-timeline-design.md`
- **Stack:** Astro static site + JSON data files + GitHub Pages
- **Pipeline:** Scanner (local Claude agent) → LLM Editor → Pre-commit hook → PR → Review Bot (GitHub Actions) → Auto-merge → Deploy

## Operating Model

- **Red-Green TDD** — write a failing test first, always. No code without a test.
- **Five Whys on every error** — trace root cause, install preventive measures, commit postmortem to `docs/postmortems/`.
- **Periodic self-reflection** — stop and reflect on process efficiency, update these instructions and memory to help future sessions avoid past mistakes.
- **Pre-commit hooks** — JSON schema linter must block invalid data from being committed.
- **GitHub Actions budget** — keep under 100 min/month. Heavy compute (scanning, LLM calls) runs locally.

## Visual Design

Book cover palette:
- Dark navy `#1a1e3a` (header, rail, text)
- Red `#e84040` (highlights, events, "Eric Ries")
- Light blue `#6cb8d6` (accents, reviews, links)
- White `#ffffff` (titles, card backgrounds)
- Light gray `#f3f4f6` (page background)
- Subtle iridescent shimmer on header

Layout: left-rail feed (dates left, content cards right).

## Content Standards

- Every entry has an LLM-written `summary` (concise, 1-2 sentences) and a `blockquote` pulled directly from the source material.
- **CRITICAL: Blockquotes must be EXACT text from the source page.** Never paraphrase, composite, or summarize — copy the exact words. Run `npx tsx scripts/verify-quotes.ts` before committing any new entries. Never trust LLM-reported "quotes" without fetching the source and confirming the text exists.
- **CRITICAL: Never create an entry if you cannot read the source page.** If a page is JS-rendered, behind auth, or otherwise unreadable, do NOT create an entry based on search result snippets or assumptions. An unverifiable entry is worse than no entry.
- **CRITICAL: Search result snippets are not evidence.** A search result mentioning "Eric Ries" on a page does not mean the page is about Incorruptible. Always fetch and read the actual page before creating an entry.
- **CRITICAL: Blockquotes must be EXACT text from the source page.** Never paraphrase, composite, or summarize — copy the exact words. Run `npx tsx scripts/verify-quotes.ts` before committing any new entries. Never trust LLM-reported "quotes" without fetching the source and confirming the text exists.
- The review bot must verify that `blockquote` text actually appears at `source_url`.
- **When citing Eric's own social posts (TikTok, Instagram, LinkedIn video), always include a screenshot/thumbnail.** Download the video cover image and save to `public/images/social/`. Every social video post must have an `image` field set.
- Prompt injection defense on all scraped content.
- Fully automated — no human review queue.

## Data

- One JSON file per entry in `content/entries/`, named by ID.
- Schema defined in the design spec.

## Search Signals

- Twitter/X: @ericries | Bluesky: @ericries
- Instagram: @ericriesactual | TikTok: @ericriesactual
- LinkedIn: https://www.linkedin.com/in/eries/ (most important)
- Web: "Eric Ries" + "Incorruptible"
