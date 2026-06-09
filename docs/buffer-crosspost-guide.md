# Buffer cross-post agent guide

You are scheduling cross-posts to Eric Ries's social channels via the Buffer MCP, drawing from a static-site archive of endorsements / reviews / podcasts / media hits for the book **Incorruptible** (Authors Equity, launched 2026-05-26). The site is **howisincorruptiblegoing.com** and lives at `/Users/EricRies2/Projects/howisincorruptiblegoing/` on this machine.

The goal isn't to dump posts into the queue. It's to **find the moments the queue is thin, slot the right asset into the right gap, and never double-post the same entry to the same channel**.

---

## Inputs you have

### Repo (read-only — DO NOT commit)
- `content/entries/*.json` — every entry on the site, one file per ID. Fields you'll use: `id`, `date`, `type`, `title`, `summary`, `blockquote`, `blockquote_source`, `attribution`, `attribution_title`, `image`, `source_url`, `type_metadata.highlight`, `type_metadata.sidebar_quote`, `tags`.
- `public/images/cards/<id>.png` — the auto-generated 1600×900 quote card with `howisincorruptiblegoing.com` watermark. Use this as the share image when `entry.image` points to `/images/cards/...`.
- `public/images/ig-cards/<id>.png` — Instagram-format 1080×1350 (4:5 portrait) quote card with watermark in the safe area. Generated on demand by `scripts/generate_ig_card.py <entry-json> public/images/ig-cards/<id>.png`. Use this for any IG-bound post. If the file doesn't exist yet for the entry, generate it before scheduling.
- `public/images/podcasts/<slug>.jpg` — 600×600 podcast covers. Use when `entry.image` points to `/images/podcasts/...`.
- `public/images/social/`, `public/images/featured/`, `public/images/events/` — other hero images. Same rule: if `entry.image` is set, that's the file to attach.
- `public/images/cards/2026-06-09-steve-blank-incorruptible.png` is a representative example to look at first to understand the card aesthetic.

### State file (you write to this)
- `data/cross-posts.json` — tracks which entries have been queued to which channel. Create it on first run. Schema:

```json
{
  "<entry-id>": {
    "bluesky": "2026-06-09T15:30:00Z",
    "x":       null,
    "instagram": null,
    "linkedin": "source"
  }
}
```

Values: ISO timestamp when scheduled, `null` if untouched, or the literal string `"source"` if the content originated on that platform (e.g. a LinkedIn endorsement was already posted to LinkedIn by the original author — no need to re-post there).

Inferring `"source"`: read `entry.source_url` and `entry.source_urls[].url`. If the domain matches the platform (`linkedin.com` → linkedin source, `x.com` or `twitter.com` → x source, `bsky.app` → bluesky source), mark that platform as source.

### Buffer MCP
You have the Buffer MCP tools. Use them to:
1. **List the channels** Eric has connected.
2. **Read the existing queue per channel** — get scheduled posts, their times, their content.
3. **Create new scheduled posts** with text + media attachment + scheduled_at.

---

## Channel priorities

Per a 2026-06-09 conversation with Eric, these are the gaps:

| Channel | State today | Daily cadence | Notes |
|---|---|---|---|
| **Bluesky** | Dark | 1–2/day | Highest priority. Founder/book audience is growing, low competition. |
| **X / Twitter** | Quiet since launch week | 1/day | Eric still has 300K+ followers there. |
| **Instagram** | Dark | 1/day (feed) | Needs 1:1 crop — see "image handling" below. |
| **LinkedIn** | Saturated already | 0–1/day | Most endorsements originate here. Only cross-post Eric's *own* content from other sources (CNBC clips, podcast pulls), NOT third-party endorsements that already lived on LinkedIn. |
| **TikTok** | Out of scope | — | Buffer doesn't reliably support TikTok; skip. |

If Bluesky has only 1 scheduled post and X has 7, prioritize Bluesky. **The number of slots you add per channel should be inversely proportional to how full that channel's queue already is.**

---

## Step 1: Audit the existing Buffer queue (do this FIRST)

Before writing any new posts, **read the queue on every channel** Eric has connected. Specifically:

1. List the channels via Buffer MCP.
2. For each channel, fetch the currently scheduled queue. You're looking for:
   - **Number of upcoming scheduled posts** per channel
   - **Time spacing** between posts (every 4 hrs? clustered at 9am/3pm/8pm? gaps of 2+ days?)
   - **Topic clustering** — back-to-back Steve Blank quotes would look spammy
   - **Posts that already cover Incorruptible content** — don't duplicate Eric's existing scheduled content

3. **Identify the gaps:**
   - Channels with < 3 scheduled posts → top priority
   - Time slots > 12 hours apart with nothing in between → ideal insertion points
   - Days with zero posts → fill those first
   - Posting times that match Eric's existing rhythm (don't invent new posting times if his pattern is morning + evening; respect it)

4. **Report what you found** before proposing posts. A quick table per channel:
   ```
   Bluesky: 0 scheduled. Last post: 2026-06-04. → ADD 3 posts over next 3 days at 9am.
   X:       7 scheduled, evenly spaced through 2026-06-12. Topic spread OK. → ADD 1 only, on 2026-06-13.
   Instagram: 1 scheduled (2026-06-10). Nothing after. → ADD 2 posts on 2026-06-11 and 2026-06-13.
   LinkedIn: 12 scheduled. → SKIP this run.
   ```

This audit is non-negotiable. Slotting blindly produces a clustered queue that looks worse than no posting at all.

---

## Step 2: Select candidate entries

Filter `content/entries/*.json` to entries that are:

1. **Recent**: `date` within the last 14 days. (Use `date 2026-06-09 -v-14d +%F` for the cutoff — but verify against current date when you run.)
2. **Have an image**: `entry.image` is not null. The file exists at `public/<entry.image>`.
3. **Have a blockquote** that's quotable: ≤ 280 chars is ideal, ≤ 200 chars is gold. If the blockquote is a full paragraph, you'll need to pull a sentence from it (see "Per-platform copy" below).
4. **Not already queued on this channel**: check `data/cross-posts.json` — if `cross-posts[id][channel]` is non-null, skip.

**Rank** the survivors by:
- `type_metadata.highlight` set → +3 points (Eric's own curation signal)
- Endorser caliber from `attribution` + `attribution_title`:
  - Household name in startup / business world (Steve Blank, Jeff Berman, Seth Godin, Mark Cuban, Frances Frei, Bob Sutton, Dan Heath) → +3
  - Recognized expert in a domain (Steen Thomsen — Copenhagen Business School; Dave Chase — Health Rosetta; Anne Lidgard — Vinnova) → +2
  - Notable founder or investor → +1
  - Otherwise → 0
- Quote punchiness — short, decontextualizable, lands without needing setup → +2 max
- Major-media hits (CNBC, Fortune, TIME, NYT, USA Today, Lit Hub) → +3
- Visual asset quality:
  - Auto-generated quote card (`/images/cards/...`) → +1 (designed for sharing)
  - Podcast cover (`/images/podcasts/...`) → 0
  - Featured photo (`/images/featured/...`, `/images/social/...`) → +1

Pick the top N for each channel based on Step 1's gap analysis. **N is usually 1–3 per channel per run.** Do not exceed 3 per channel; Buffer queues feel spammy beyond that.

---

## Step 3: Generate per-platform copy

The character limits are hard; the tone differences are real.

### Bluesky (300 chars including URL)
Format:
```
"<short pull quote — 120-180 chars>"

— <attribution>, <attribution_title (short version)>

<permalink>
```

Example for Steve Blank entry (id: `2026-06-09-steve-blank-incorruptible`):
```
"This book will possibly be more important than the Lean Startup ever was — for you, your company and society as a whole."

— Steve Blank, customer-development pioneer

https://howisincorruptiblegoing.com/e/2026-06-09-steve-blank-incorruptible/
```

If the blockquote is too long, pull the single most quotable sentence — usually the one used in `type_metadata.sidebar_quote` or `type_metadata.highlight`. Never paraphrase; only excerpt.

### X / Twitter (280 chars)
Same format as Bluesky but tighter:
```
"<even shorter pull — 100-150 chars>"

— <attribution>

<permalink>
```

URL costs ~23 chars after t.co shortening. Budget your text accordingly.

### Instagram (caption is long, but image leads)
Image first. Caption format:
```
<the pull quote — full sentence or two>

— <attribution>, <attribution_title>

<1 sentence of context about why this matters>

Full thread → link in bio (howisincorruptiblegoing.com)

#Incorruptible #EricRies #<1-2 relevant tags from entry.tags>
```

Instagram doesn't allow clickable links in captions — say "link in bio" rather than dropping a dead URL.

### LinkedIn (long-form OK)
Only post here if cross-posting Eric's *own* media (CNBC clip, podcast pull). Format like Eric's own posts: 2-3 short paragraphs, conversational, ends with the URL. **Don't cross-post third-party endorsements that already originated on LinkedIn** — they're already in the LinkedIn algo as their original author's post.

---

## Step 4: Image handling

**Always attach an image to scheduled posts when one exists.** A bare URL on Bluesky/X is dramatically worse engagement than a card.

- **Quote cards** (`/images/cards/<id>.png`, 1600×900) — attach as-is to Bluesky, X, LinkedIn. They render correctly in the feed.
- **For Instagram feed:** use the matching 4:5 portrait card at `public/images/ig-cards/<id>.png`. If the file doesn't exist yet, generate it before scheduling:
  ```bash
  uv run --with pillow python scripts/generate_ig_card.py \
    content/entries/<id>.json \
    public/images/ig-cards/<id>.png
  ```
  The card is 1080×1350 with the `howisincorruptiblegoing.com` watermark in the safe area. Never crop the 1600×900 card for IG — it cuts off the watermark.
- **Podcast covers** (`/images/podcasts/<slug>.jpg`, 600×600) — already 1:1, work on every channel.
- **Featured photos** (`/images/featured/<id>.jpg`, `/images/social/<id>.jpg`) — varies; check aspect ratio before posting.

The file path on disk for an entry's image is always: `public/<entry.image>` (e.g. `public/images/cards/2026-06-09-steve-blank-incorruptible.png`).

---

## Step 5: Schedule into the optimal slot

Based on the Step 1 audit:

- **If the queue is empty or has a multi-day gap:** schedule at a sensible posting time within Eric's existing rhythm. Default to 9:00 AM and 3:00 PM local (America/Los_Angeles). If existing posts cluster at e.g. 8:47 AM, use 8:47 AM, not a round number.
- **If the queue has good time spread but a topic cluster you're about to add to:** push your new post outside the cluster. Don't slot a Steve Blank quote next to another Steve Blank quote — leave at least 48 hours between mentions of the same person.
- **If multiple posts for the same entry need to land on different channels:** stagger them across days. A Bluesky post on Monday, X on Tuesday, IG on Wednesday. Same content hitting all three on the same day reads as automation noise to anyone following Eric on more than one platform.

Use the Buffer MCP's create/schedule call. Confirm via the response that the post is queued at the right time. If the response surfaces an error (e.g. character limit exceeded, image format unsupported), fix the input and retry — don't ship a broken post.

---

## Step 6: Update `data/cross-posts.json`

After each successful schedule:
1. Read `data/cross-posts.json` (create with `{}` if missing).
2. For the entry just scheduled, set `data["<entry-id>"]["<channel>"] = "<scheduled_at ISO timestamp>"`.
3. Write back the file with 2-space indent.
4. Do NOT commit this file to git in this run — Eric will review and commit periodically.

**Backfill is already wired up.** If `data/cross-posts.json` is missing or appears empty of `"source"` markers, run the backfill CLI before Step 1:

```bash
uv run python scripts/backfill_cross_posts.py \
  --entries-dir content/entries \
  --state-file data/cross-posts.json
```

The CLI walks `content/entries/*.json`, infers source markers from each entry's `source_url` and `source_urls[].url` (via `scripts/lib/cross_posts.py`), and merges them into the state file. It's idempotent — existing scheduled timestamps are always preserved over inferred source markers. As of 2026-06-09 the production state file has 183 LinkedIn / 20 X / 1 Bluesky source markers across 201 entries.

---

## Quality bar (do not violate)

- **Never paraphrase a blockquote.** The site enforces exact-text-from-source. Cross-posts must too. If the quote needs trimming, pull a contiguous sentence; don't stitch fragments.
- **Never invent an attribution title.** Use `entry.attribution_title` verbatim, or a tighter known-correct version (e.g. "Customer-development pioneer; Adjunct Professor, Stanford" → "Customer-development pioneer" for char budget). Do not promote a "Co-founder" to "Co-founder & CEO" without source.
- **Never post a card with the watermark cropped off.** The watermark is the call-to-action back to the site.
- **Never schedule a post Eric himself would not approve.** If a candidate makes you hesitate (potential political read, off-brand humor, low-credibility endorser), skip it and flag it in your report.
- **One entry, one channel, ever.** If `data/cross-posts.json` says an entry was posted to Bluesky on 2026-06-09, do not re-post it to Bluesky again on 2026-07-09 to "refresh" the queue. Find fresh content instead.
- **AI-generated TikToks are blocked at the source.** If you're ever asked to extend this to TikTok, read `~/.claude/projects/-Users-EricRies2-Projects-howisincorruptiblegoing/memory/feedback_no_ai_tiktoks.md` first.

---

## Report back

When you finish, give Eric a single-screen report:

```
Buffer queue audit:
- Bluesky: 0 → 3 scheduled (next: 2026-06-10 09:00, 2026-06-11 09:00, 2026-06-13 09:00)
- X: 7 → 8 scheduled (added 2026-06-13 09:00)
- Instagram: 1 → 3 scheduled (added 2026-06-11 09:00, 2026-06-13 09:00)
- LinkedIn: skipped (queue full)

Entries used:
- 2026-06-09-steve-blank-incorruptible → Bluesky, X, Instagram (staggered)
- 2026-06-08-cnbc-squawk-box-ai-anthropic → Bluesky
- 2026-06-08-think-fast-talk-smart-matt-abrahams → Instagram

Skipped:
- 2026-06-09-dave-chase-relocalizing-health (no IG crop, but Bluesky-able next run)
- 2026-06-07-jeff-berman-goodreads (already source-marked on LinkedIn)

State file updated at data/cross-posts.json.
```

Keep it under 250 words. Don't narrate the audit process — just the result.

---

## When in doubt

1. Read `CLAUDE.md` at the repo root for site-wide editorial norms.
2. Read `~/.claude/projects/-Users-EricRies2-Projects-howisincorruptiblegoing/memory/MEMORY.md` for accumulated rules — especially `feedback_writing_tone.md`, `feedback_attribution_titles.md`, and `feedback_quote_capitalization.md`.
3. If a candidate entry doesn't pass the quality bar, **skip it and report it as skipped** rather than degrading the post to make it fit. An under-full queue is better than a queue full of weak posts.
