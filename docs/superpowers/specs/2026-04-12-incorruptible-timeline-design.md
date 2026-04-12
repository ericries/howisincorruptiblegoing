# How Is Incorruptible Going? — Design Spec

**Date:** 2026-04-12
**Author:** Eric Ries + Claude
**Status:** Draft

## Purpose

A public timeline website tracking momentum for Eric Ries's book *Incorruptible* (publishing May 26, 2026). The site creates a sense of "a LOT is happening" by surfacing every endorsement, event, review, podcast, social post, and milestone as its own timeline entry with a unique date. Content is discovered automatically by a scanning agent and published without human review, gated by a rigorous multi-layer validation pipeline.

Inspired by [web3isgoinggreat.com](https://www.web3isgoinggreat.com/) (timeline format, per-entry structure) but positive in tone, aligned with the Incorruptible brand.

## Visual Design

### Layout: Left-Rail Feed

Reverse-chronological timeline. Dates appear in a left rail, content cards to the right, connected by a vertical timeline line with colored dots at each entry.

- Dates: right-aligned in a fixed-width left column (day + year)
- Timeline rail: 2px navy vertical line with colored dot markers (red or light blue, alternating by type)
- Content cards: white background, subtle shadow, pill-shaped category badges
- Collapses to single-column on mobile (date above card)

### Color Palette (from the book cover)

| Role | Color | Hex |
|------|-------|-----|
| Primary background (header, rail, text) | Dark navy | `#1a1e3a` |
| Primary highlight (events, "Eric Ries", countdown) | Red | `#e84040` |
| Secondary accent (reviews, links, subtitles) | Light blue | `#6cb8d6` |
| Title text, card backgrounds | White | `#ffffff` |
| Page background | Light gray | `#f3f4f6` |
| Iridescent shimmer | Gradient overlay on header | `linear-gradient(135deg, rgba(108,184,214,0.06), rgba(255,255,255,0.03), rgba(232,64,64,0.04), rgba(108,184,214,0.06))` |

### Header

- Dark navy background with subtle iridescent overlay
- "HOW IS" in light blue, small caps, letterspaced
- "INCORRUPTIBLE" in white, bold, large, letterspaced
- "GOING?" in light blue, small caps, letterspaced
- Subtitle: "The new book by **Eric Ries** · May 26, 2026" (name in red)

### Stats Bar

Below the header, dark navy (#151833) background:
- Days to launch (red)
- Total entries (light blue)
- Total endorsements (white)

### Entry Card Anatomy

Each card contains:
- **Category badge** — pill-shaped, colored by type (navy for events, red for reviews, light blue for endorsements, etc.)
- **Title** — bold, navy text
- **Summary** — LLM-written, 1-2 concise sentences
- **Blockquote** — direct quote from source material, italicized
- **Blockquote source** — attribution line below the quote
- **Image** — optional, displayed below text when present
- **Source link** — light blue "→ Read full [type]" link
- **Attribution photo** — circular headshot for endorsement entries, displayed left of content

## Data Model

### Entry Schema

Each entry is a single JSON file stored in `content/entries/`, named by ID.

```json
{
  "id": "2026-04-10-long-now-event",
  "date": "2026-04-10",
  "type": "event",
  "title": "Long Now Foundation",
  "summary": "Eric presents at Long Now on institutional design, arguing that lasting organizations require fundamentally new governance structures.",
  "blockquote": "Ries opened with a provocation: 'Every institution you trust today was designed to be corruptible. What if we could do better?'",
  "blockquote_source": "Long Now Blog",
  "source_url": "https://longnow.org/...",
  "image": "images/long-now-event.jpg",
  "attribution": null,
  "attribution_title": null,
  "attribution_image": null,
  "tags": ["speaking", "institutions"],
  "type_metadata": {},
  "scanner_source": "web-search",
  "verified": true,
  "created_at": "2026-04-11T08:30:00Z"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique ID, format: `YYYY-MM-DD-slug` |
| `date` | string | yes | Display date, ISO 8601 date |
| `type` | enum | yes | One of: `event`, `endorsement`, `review`, `social`, `podcast`, `media`, `milestone` |
| `title` | string | yes | Short, descriptive title |
| `summary` | string | yes | LLM-written concise summary, 1-2 sentences |
| `blockquote` | string | yes | Direct quote from source material |
| `blockquote_source` | string | yes | Human-readable name of the source |
| `source_url` | string | yes | URL of the original source |
| `image` | string | no | Path to image file, relative to `content/` |
| `attribution` | string | no | Person's name (for endorsements) |
| `attribution_title` | string | no | Person's title/role |
| `attribution_image` | string | no | Path to person's headshot |
| `tags` | string[] | yes | Categorization tags |
| `type_metadata` | object | no | Type-specific extra data |
| `scanner_source` | string | yes | How the entry was found: `web-search`, `social-scan`, `manual`, `rss` |
| `verified` | boolean | yes | Set true by review bot |
| `created_at` | string | yes | ISO 8601 datetime of entry creation |

### Entry Types

| Type | Badge Color | Use |
|------|-------------|-----|
| `event` | Navy | Speaking engagements, book tour stops, panels |
| `endorsement` | Light blue | Blurbs, testimonials (uses attribution fields) |
| `review` | Red | Published reviews, newsletter mentions |
| `social` | Navy | LinkedIn posts, tweets, Bluesky posts |
| `podcast` | Red | Podcast appearances, audio interviews |
| `media` | Light blue | News articles, TV segments, press coverage |
| `milestone` | Red | Publication date, bestseller list, pre-order milestones |

## Content Pipeline Architecture

### Overview

Three independent stages, each testable in isolation. The scanner never writes directly to main — every entry goes through a PR.

```
Scanner finds content (local, Claude Code scheduled agent)
  → LLM Editorial Review polishes entry (local)
    → Pre-commit hook validates schema (local)
      → PR opened against repo
        → Review Bot verifies independently (GitHub Actions)
          → Auto-merge
            → Site builds and deploys (GitHub Actions)
```

### Stage 1: Scanner (Local — Claude Code Scheduled Agent)

Runs 1-2x daily via Claude Code `/schedule`. Searches for new content:

**Search targets:**
- Twitter/X: @ericries
- Bluesky: @ericries
- Instagram: @ericriesactual
- TikTok: @ericriesactual
- LinkedIn: https://www.linkedin.com/in/eries/ (highest priority)
- Web search: "Eric Ries" + "Incorruptible", "Incorruptible" + "book"
- RSS feeds of known publications covering the book

**For each new find:**
1. Fetch the source page
2. Write an LLM summary (concise, 1-2 sentences)
3. Extract the best blockquote from the source
4. Download or reference an image where available
5. Generate the JSON entry file

### Stage 2a: LLM Editorial Review (Local — Before PR)

A strict LLM editor reviews each entry before the PR is opened. This is the "editor-in-chief" ensuring quality, not just correctness.

**Checks:**
- Is the summary concise and compelling? (Rewrites if not)
- Is the blockquote the most interesting/relevant passage from the source?
- Is the title clear and specific?
- Is the tone appropriate for a book launch? (Positive, excited, professional)
- Does the summary faithfully represent the source material?
- Is this entry genuinely noteworthy, or is it noise?

Scores each entry. Entries below threshold are rewritten or rejected.

### Stage 2b: Pre-Commit Hook (Local — On Every Commit)

Deterministic JSON schema linter, no network calls, no LLM. Blocks commits with malformed data.

**Validates:**
- JSON parses correctly
- All required fields present
- Field types match schema
- `date` is valid ISO 8601
- `type` is a valid enum value
- `id` matches `YYYY-MM-DD-slug` format
- `source_url` is a valid URL
- Character limits respected
- No empty required string fields

### Stage 3: Review Bot (GitHub Actions — On PR)

Independent verification, completely separate execution context from the scanner. Cannot be influenced by scanner or local editor.

**Checks:**
- **Schema validation** — re-runs the same linter as the pre-commit hook
- **Quote verification** — fetches `source_url`, confirms `blockquote` text actually appears in the page content
- **Prompt injection detection** — scans all text fields for injection patterns, suspicious unicode, encoded payloads, HTML/script tags
- **Duplicate detection** — checks existing entries for same `source_url` or near-duplicate titles/summaries
- **Image validation** — if image referenced, confirms file exists and is a reasonable size
- **Content policy** — checks for profanity, off-brand language, potentially harmful content

Each check is independent — any single failure blocks the PR with a clear, specific error message. All checks must pass for auto-merge.

### Stage 4: Build & Deploy (GitHub Actions — On Merge to Main)

- Astro reads all JSON entries from `content/entries/`
- Builds the static timeline HTML
- Deploys to GitHub Pages

## Tech Stack

| Component | Technology | Reason |
|-----------|-----------|--------|
| Static site generator | Astro | Fast builds, content-driven, island architecture for optional interactivity |
| Data storage | JSON files in git | Full history, clean diffs, easy rollback, no external DB |
| Hosting | GitHub Pages | Free, reliable, matches existing seedlist.com workflow |
| CI: Review bot + deploy | GitHub Actions | Independent execution context, required PR checks |
| Scanner + editor | Claude Code scheduled agent | Runs locally, avoids Actions minute costs |
| Testing | Vitest (or similar) | Fast, modern, good Astro integration |
| Linting | Custom JSON schema validator + ESLint | Pre-commit hook for schema, ESLint for code |
| Pre-commit hooks | Husky + lint-staged | Industry standard, reliable |

### GitHub Actions Budget

Designed to stay well under the free tier (2,000 min/month):
- ~2 PRs/day × ~1 min (review bot) = ~60 min/month
- ~2 deploys/day × ~0.5 min (Astro build) = ~30 min/month
- **Estimated total: ~90 min/month**

All heavy compute (web scraping, LLM calls for scanning and editorial review) runs locally via the Claude Code scheduled agent.

## Operating Model

### Red-Green TDD

All code is written test-first, no exceptions.

1. **Red** — write a failing test that describes the desired behavior
2. **Green** — write the minimum code to make it pass
3. **Refactor** — clean up while keeping tests green

Applies to: JSON schema validator, prompt injection detector, quote verifier, editorial scorer, timeline rendering, scanner logic, review bot checks. If it's code, it has a test that was written first.

### Five Whys on Every Error

When something goes wrong — a bad entry gets through, a build fails, a test is flaky, a scanner misidentifies content — we don't just fix it:

1. Why did this happen?
2. Why did that cause happen?
3. Why wasn't it caught?
4. Why didn't our safeguards prevent it?
5. Why didn't we have those safeguards?

Then install a preventive measure: a new test, a new linter rule, a new validation step, a new editorial check. Each class of error can only happen once. The system gets stricter over time.

Five Whys artifacts are committed to `docs/postmortems/` so future sessions can learn from past mistakes.

## Search Signals for Scanner

**Social accounts:**
- Twitter/X: @ericries
- Bluesky: @ericries
- Instagram: @ericriesactual
- TikTok: @ericriesactual
- LinkedIn: https://www.linkedin.com/in/eries/

**Search queries:**
- "Eric Ries" + "Incorruptible"
- "Incorruptible" + "book"
- "Eric Ries" + "book" + 2026

**Known early coverage to seed:**
- Long Now Foundation event
- Ari Shapiro newsletter review
- Official book blurbs (Eric will provide)
- Test reader testimonials spreadsheet (Eric will provide)

## Content Seeding

The initial launch needs enough entries to look impressive. Sources for backfill:
1. Official blurbs (Eric to provide) — each as its own entry with endorser photo
2. Test reader testimonials (Eric to provide spreadsheet) — selected quotes as entries
3. Past events and podcasts — scanner will search and backfill
4. Eric's own social posts about the book — scanner will find these
5. Known coverage (Long Now, Ari Shapiro, etc.) — scanner will find and create entries

Each backfilled entry gets a historically accurate date to create a realistic timeline of building momentum.

## Security Considerations

### Prompt Injection Defense

All scraped content is untrusted input. The review bot scans for:
- Known injection patterns ("ignore previous instructions", "system:", etc.)
- Suspicious unicode (homoglyphs, zero-width characters, RTL overrides)
- Encoded payloads (base64, URL encoding, HTML entities)
- HTML/script tags in text fields
- Anomalously long field values

The scanner and review bot are independent systems — even if scraped content tricks the scanner's LLM, the review bot's pattern-matching checks catch injection attempts.

### Data Integrity

- Git history provides a complete audit trail of every entry
- Pre-commit hook prevents malformed data from entering the repo
- Review bot independently verifies all claims (quotes exist at source URL)
- Any bad entry can be reverted with a single git commit
- The scanner never has direct write access to main branch
