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

**Never hardcode `postedLimit`. Derive it.** These crons only fire while the
REPL is idle, so a closed laptop means a cycle simply does not happen — and a
fixed `"24h"` window can never reach back over the day it missed. That is not
hypothetical: the evening scan did not run on 2026-10-12, and the next day's
24h window silently skipped past three posts at 108, 81 and 68 reactions. They
surfaced four days later only because someone asked.

```python
import sys; sys.path.insert(0, "scripts")
from scan_state import choose_posted_limit, read_watermark, write_watermark, record_run, clear_run

src  = "linkedin-keyword"                      # or linkedin-mentions, youtube, ...
when = choose_posted_limit(read_watermark(src), NOW_ISO)   # "24h" on schedule, wider after a gap
# ... call the actor with postedLimit=when ...
record_run(dataset_id, actor=..., label=src, launched_at=NOW_ISO)   # survives a dead turn
# ... archive + triage ...
clear_run(dataset_id); write_watermark(src, NOW_ISO)       # only after the archive is written
```

On schedule this returns `"24h"` and costs exactly what it did before; it widens
only as far as the actual outage requires. **A widened window always needs
client-side dedup** against `data/archive/` — `scan-triage.py` already marks
`SHIPPED`, and the catch-up pattern in the 2026-10-16 health check shows the
rest.

`record_run` exists because on 2026-10-15 a turn launched six Apify runs and
ended before triage; the dataset ids lived only in conversation context and the
paid data was nearly lost. Write them to disk at launch, clear them after triage.

**Always pass `callOptions: {maxItems: N}`.** These actors bill per dataset
item, and `maxPosts` is a soft target the actor does not honour: on 2026-10-14
the comment-archive runs were given `maxPosts: 30` and `maxPosts: 40` and
returned **130 posts each**. `maxItems` is the only hard billing cap. Measured
over Oct 10-14, the two comment-archive runs alone were 763 of ~1,524 items
pulled — **50% of all Apify volume for a job that ships nothing to the site**.

Standing caps (raise only with a reason, and say so in the report):

| job | call | maxItems |
|---|---|---|
| comment archive | author feed | 40 |
| comment archive | keyword | 40 |
| morning scan | LinkedIn ×2 | 25 each |
| evening scan | LinkedIn @-mentions | 25 |
| weekly audit | each of 3 | 100 (needed for a valid comparison) |

Apify is on a **$29/month** limit and hit 50% by Oct 14. When a scan's triage
shows the cap was reached and the tail still looked relevant, say so in the
report rather than silently raising it.

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
`--full <N>`.** People regularly use "incorruptible" as a plain adjective near
the top of a post and credit the book further down, so the opening is the least
reliable place to judge from.

Since 2026-10-16 `render_row` compensates: when the book mention falls past the
truncation point it shows the opening *and* the sentence carrying the citation,
separated by `… […] …`. A row in that shape is telling you the author buried
the reference — on the pull that was measured, a third of posts did. That makes
the row safe to scan, but it is still a preview: `--full` remains the rule
whenever the decision is close.

**A short list is not a reason to skim.** The daily keyword pull is often under
15 items, and the temptation is to clear it on the triage rows alone. The
2026-10-11 recall audit found the week's best founder-application post (Fora
Fereydouni, Cognitai, 47 likes) had been passed over inside a 13-item list and
reached the site a week late. Volume is never the thing that hides a candidate —
reading only the first 150 characters is.

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
