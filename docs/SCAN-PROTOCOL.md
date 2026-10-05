# Scan protocol

The standing rules for every content scan. Cron prompts point here instead of
restating this, so the rules live in version control and the prompts stay short.

> Node: `export PATH="/opt/homebrew/opt/node@23/bin:$PATH"` before npm/npx.

---

## 1. Running an Apify actor

**Always `waitSecs: 0`.** The waiting path returns the actor's full field schema
on every call — measured at 9,630 chars vs 609 for `waitSecs: 0`, 15.8x more,
and none of it is ever used. The three Apify MCP tools were 69% of all tool
traffic in the session measured on 2026-10-04.

```
1. mcp__apify__call-actor  { actor, input, waitSecs: 0 }   -> runId + datasetId
2. python3 scripts/scan-triage.py <datasetId> \
       --platform linkedin|twitter|tiktok|youtube \
       --archive data/archive/<src>-raw/<YYYY-MM-DD>-<scan>.json
```

Step 2 polls until the dataset is populated, archives the raw items (this is what
satisfies the full-source-text requirement in §5), and prints a compact triage
table. **Never use `get-dataset-items` or `get-actor-run`** — `scan-triage.py`
replaces both.

Useful flags: `--since YYYY-MM-DD`, `--new-only`, `--width N`.

**If an Apify call hangs silently (no error, several minutes):** that is *not*
the stale-session signature (which errors explicitly with "Session ID not
found"). Retry once with `waitSecs: 0`; if that returns promptly the transport is
healthy and only the long-poll is wedged — carry on. A genuine stale session
needs the user to `/mcp` reconnect; tell them and wait rather than degrading to
WebSearch.

## 2. Reading candidates

`scan-triage.py` marks each row:

- **`SHIPPED`** — this `source_url` is already on the timeline.
- **`AUTHOR-HAS-N`** — this author already has N entries, listed by id. The same
  person twice in a week is usually one entry; ship the second only if it says
  something genuinely new.
- **`SLIDESHOW`** — TikTok photo post, Eric is not on camera.

**When a ship/skip decision turns on what a post actually says, run
`--full <N>`.** Never decide from the truncated row. People regularly use
"incorruptible" as a plain adjective near the top of a post and credit the book
further down, so the opening is the least reliable place to judge from.

## 3. Inclusion bar

Judge against the memory files — they hold the accumulated standards and are the
authority:

`feedback_entry_inclusion` · `feedback_third_party_concept_attribution` ·
`feedback_tag_is_not_reference` · `feedback_no_critical_reviews` ·
`feedback_goodreads_inclusion` · `feedback_founder_applying_framework` ·
`feedback_judge_reach_at_destination` · `feedback_event_dates` ·
`feedback_event_recap_not_new_event` · `feedback_no_ai_tiktoks`

Recurring traps, in short:

- **An @-tag is not a reference.** The body must engage with the book.
- **Judge reach at the destination, not the referrer.** Resolve the link; check
  iTunes / `numberOfSubscribers` / the masthead. Record it in
  `type_metadata.audience`. Set `source_url` to the episode or article itself,
  never the LinkedIn post announcing it — What's New eligibility keys off it.
- **Events need organiser-side corroboration.** One attendee announcing their own
  invitation establishes that *they* are going. Confirm Eric's participation and
  session title on the organiser's page or RSVP, or hold it in
  `data/archive/pending-verification/`.
- **Check the true publication date.** A YouTube upload can post an episode
  months after it aired; check the RSS feed or Apple Podcasts.
- **No critical or mixed reviews.** The site tracks momentum.

### @ericriesactual TikTok — blocking rule

Before shipping any TikTok, grep its id against **`data/ai-tiktok-denylist.json`**
(79 ids, in this repo so it survives a platform change) **and** confirm Eric is
on camera:

```sh
python3 -c "import json,sys; d={r['id'] for r in json.load(open('data/ai-tiktok-denylist.json'))['denylist']}; print(sys.argv[1] in d and 'DENIED' or 'not on denylist — still verify on-camera')" <VIDEO_ID>
```

The list only grows; add ids as they are identified and never remove one.
`memory/feedback_no_ai_tiktoks.md` holds the longer narrative. Caption content is not a
reliable signal. The podcast-cutout pattern ("X and I discuss…") is animated by
default. Photo slideshows (`isSlideshow: true`, duration 0) never qualify. If you
cannot confirm on-camera, skip. This rule has been violated three times.

## 4. Writing an entry

- Blockquote must be **exact, contiguous text** from the source. Never
  paraphrase, composite, or stitch across paragraphs. Transcripts are the one
  exception: light cleanup of ASR artefacts is allowed and expected.
- Every entry gets a **real image**: headshot to `/images/people/<slug>.jpg`
  (LinkedIn `og:image` on the public profile URL works where the Apify profile
  scraper returns nothing), podcast cover to `/images/podcasts/<slug>.jpg` via
  the iTunes API `artworkUrl600`, event art to `/images/events/`. The quote card
  is a fallback, not the default.
- Title leads with the quote where there is one; preserve the source's
  capitalisation inside the quoted span. Cap 200 characters.
- Sidebar flags per `feedback_sidebar_flags`. `highlight` requires a name on
  `HIGHLIGHT_ELIGIBLE_ENDORSERS` — adding one is Eric's call, asked via
  AskUserQuestion, never in prose.

## 5. Archive, verify, ship

```
python3 scripts/backfill-quote-cards.py      # before lint — wires entry.image
python3 scripts/backfill-source-texts.py     # full source text, verbatim
npx tsx scripts/verify-quotes.ts
npx tsx scripts/lint-entries.ts              # read the trailing summary line
git add <specific paths> && git commit && git push
```

For YouTube entries also save the transcript to
`data/archive/transcripts/<entry-id>.txt`.

Occasionally: `python3 scripts/backfill-source-texts.py --audit` flags published
blockquotes that no longer appear verbatim in the stored source. It deliberately
skips transcript-sourced entries, since those are cleaned by design.

The pre-commit hook runs lint + vitest + verify-quotes and takes **about 12
seconds** (measured 2026-10-04). Never `--no-verify`.

## 6. Reporting

Lead with the biggest signal of the cycle, not the logistics. Quote the punchy
line. Then: what shipped, what was skipped **and why** (every below-bar candidate
gets a verbatim or paraphrase line plus a concise reason), and anything held for
verification. Corrections to earlier reports go near the top, stated plainly.
