# Scanner crons — canonical definitions

**This file is the source of truth.** Any agent, on any platform, can restore the
full scanning schedule by reading it. Nothing lives outside this repository: no
launchd agents, no system background items, no machine-local state.

## At the start of every session

1. Run `CronList`.
2. Recreate any job below that is missing, with `CronCreate`, copying the cron
   expression and prompt verbatim.
3. Report in one line which were restored, or "all 7 present".

Session crons are in-memory and vanish when the session ends; the runtime also
silently ignores `durable: true`, and recurring jobs auto-expire after 7 days.
Restoring them at session start is therefore normal and expected, not a sign
something broke.

The standing rules each job follows live in [`SCAN-PROTOCOL.md`](SCAN-PROTOCOL.md).
Prompts point at it rather than restating it, which keeps the rules in version
control and the prompts short.

| job | cron | purpose |
|---|---|---|
| Watchdog | `17 8 * * *` | restores any missing job, renews itself |
| Morning scan | `7 9 * * *` | LinkedIn ×2 + X + YouTube + WebSearch |
| Goodreads | `33 10 * * 1` | Goodreads reviews (Mondays) |
| Comment archive | `47 10 * * 1,3,5` | LinkedIn comment superlatives (local only) |
| Recall audit | `17 11 * * 0` | query-calibration drift (Sundays) |
| Evening scan | `3 18 * * *` | TikTok + LinkedIn/X mentions |
| Sidebar curation | `27 19 * * *` | What's New / Highlights |

**Paused:** Amazon rank scan, `43 17 * * 1,4`. Paused at Eric's request
2026-08-31 when the 90-day New Release window closed. Do not recreate it unless
he asks.

---

## 1. Watchdog — `17 8 * * *`

```
Cron watchdog. Run CronList. These must be present (Amazon rank is paused — do NOT recreate "43 17 * * 1,4" unless the user asks):

1. Morning content scan — "7 9 * * *"
2. Goodreads review scan — "33 10 * * 1"
3. LinkedIn comment archive scan — "47 10 * * 1,3,5" (Mon/Wed/Fri)
4. Evening content scan — "3 18 * * *"
5. Sidebar curation — "27 19 * * *"
6. Weekly LinkedIn recall audit — "17 11 * * 0"
7. This watchdog — "17 8 * * *"

Recreate any that are missing using the verbatim prompts in docs/CRONS.md.

STEP 1 — ROLL ALL SEVEN JOBS, NOW, BEFORE ANYTHING ELSE. Do the morning scan first.

ROLLING SELF-RENEWAL is why this job exists. Recurring crons auto-expire 7 days after creation. The watchdog can never catch its own expiry by checking CronList, because it stays listed right up until it dies — and when it dies, every other cron follows at its own 7-day mark with nothing left to restore them. That is the single point of failure in the whole system. So roll every job every run, even when nothing is missing: for each of the seven, CronCreate a replacement carrying its current live prompt forward verbatim, then CronDelete the old id. On 2026-10-13 five daily jobs expired as a cohort because they had all been created together.

Carry the LIVE prompt forward, not the one in docs/CRONS.md — the live prompts accumulate each day's lessons and CRONS.md lags behind them. CronList truncates, so read the full text from CRONS.md only for a job you are recreating from scratch. If you notice CRONS.md has drifted, re-sync it in STEP 2 and commit.

THE WATCHDOG MUST BE FAST. You fire at 8:17; the morning scan fires at 9:07. Creating a replacement job after its fire time has passed sets its next run to tomorrow, so that day's scan is simply lost — and a cron cannot fire at all while this turn is still running, so a long watchdog turn swallows the 9:07 slot even when the rolls were done correctly. Both failures have happened: on 2026-10-19 a YouTube backfill pushed the rolls past 9:07, and on 2026-10-20 the rolls were done first but the turn itself ran to 9:14. So: finish STEP 1 within the first few minutes, and do NOT start work in STEP 2 that could still be running at 9:00 — defer it to the morning scan or a later turn instead.

Guard: if you are somehow already past 9:07 when you start, do NOT roll the morning scan — leave it alone so it can still fire, and roll it tomorrow. Roll the other six as normal.

STEP 2 — only after all seven rolls are done.

Run the coverage check; it is free and catches what the commit log hides:

    python3 scripts/scan-coverage.py --days 14

It reports days a daily source never pulled, and any Apify run launched but never triaged. Both come from the same cause: these crons only fire while the REPL is idle, so a closed laptop silently skips cycles. On 2026-10-12 the commit log looked healthy — other cycles ran that day — while the @-mention pull had not happened at all, hiding three posts at 108, 81 and 68 reactions. Backfill an open gap with a widened postedLimit (scan_state.choose_posted_limit) and dedup against the archive, THEN acknowledge it so it stops reporting: scan_state.ack_gap(source, date, note="how it was backfilled"). Catch-up files are deliberately not counted as coverage, so without an ack a fixed gap reports forever and the report becomes noise nobody reads (found 2026-10-17 by running the tool). Triage orphaned datasets before launching anything new; they are already paid for. If a backfill looks like it will take more than a few minutes, hand it to the morning scan rather than running past 9:00.

Then sanity-check that the pipeline is producing: `git log --since="36 hours ago" --oneline` should normally show commits from the daily scans. A quiet week alongside healthy runs is possible; a quiet week is still worth flagging. Also check `git status` for uncommitted content edits left behind by a dead turn — on 2026-10-20 a corrected event entry was sitting in the working tree. data/cross-posts.json, data/events-posted.json, data/site-spotlight.json and public/documents/ are the social cross-posting tooling's own state; leave those alone.

EVENT PIPELINE — this is ANSWERED, stop flagging it nightly. A targeted search on 2026-10-20 found no November or December dates that were not already on the timeline (the one hit, Book Passage with Alex Komoroske, was the 2026-06-03 event already shipped), and a source calls the B Academics roundtable one of the final stops of the tour. SOSV Deep Tech Summit on 2026-11-04 is the last scheduled event. Raise it ONCE more when that slot actually empties, then stop — see memory/project_event_pipeline_winding_down.md.

Report which crons you restored, the roll lines "<name>: <old-id> -> <new-id>" for all seven, the coverage-check result, and anything that looked wrong.
```

## 2. Morning content scan — `7 9 * * *`

```
Morning content scan. Follow docs/SCAN-PROTOCOL.md in the repo for the full standing rules (Apify call pattern, inclusion bar, TikTok blocking rule, entry/image/verify/ship steps, reporting format). Read it first.

Sources this cycle — run each with waitSecs:0, then scan-triage.py per the protocol:
1. LinkedIn keyword, TWO queries (harvestapi/linkedin-post-search, postedLimit="24h", maxPosts=40, sortBy="date", callOptions {"maxItems": 25}):
   (a) searchQueries=["Incorruptible Ries"]
   (b) searchQueries=["Incorruptible"] — filter results yourself for book relevance; expect to discard roughly half.
   Both are needed: LinkedIn multi-word search is not a reliable AND over post text. The 2026-10-04 audit found 5 relevant posts (b) caught and (a) missed, two of which contained BOTH terms — including Raj Sisodia, author of Conscious Capitalism. Never use the 3-word "Incorruptible Eric Ries" variant; audited twice, it adds nothing. See memory/feedback_linkedin_query_calibration.md.
2. Twitter/X keyword (apidojo/tweet-scraper, searchTerms=["Incorruptible Eric Ries"], maxItems=20).
3. YouTube keyword (streamers/youtube-scraper, searchQueries=["Eric Ries Incorruptible"], maxResults=15, sortingOrder="date", dateFilter="week"). Do NOT pay for Apify subtitles — pull transcripts free with the youtube-transcript-api one-liner in the protocol. Confirm the video substantively discusses Incorruptible before shipping; a name-drop is not enough. Check the RSS feed or Apple Podcasts for the true original publication date — a YouTube upload can post an episode months after it aired.
4. WebSearch for "Eric Ries" "Incorruptible" recent mentions.

Also: pick 2-3 unimaged older entries from the backlog and source photos. Query for them with BOTH image and attribution_image null. THIS SEAM IS DRY as of 2026-10-17 — YouTube thumbnails exhausted; all 468 archived LinkedIn posts indexed by activity id against the 93 LinkedIn-sourced unimaged entries gave ZERO matches (they predate the archive); Luma publishes no og:image; the rest is paywalled (TIME, NYT) or small orgs with no social card. Report "no new image found" rather than forcing a weak one.

Finish with backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 3. Goodreads review scan — `33 10 * * 1`

```
Goodreads review scan. Follow docs/SCAN-PROTOCOL.md for the shared rules (Apify waitSecs:0 pattern, entry/image/verify/ship steps, reporting format).

Pull recent reviews via Apify: easyapi/goodreads-review-scraper with bookUrls=["https://www.goodreads.com/book/show/242970642-incorruptible"], maxItems=30. Use waitSecs:0, then curl the dataset and archive it to data/archive/goodreads/<YYYY-MM-DD>.json.

Inclusion bar — the general rule in memory/feedback_entry_inclusion.md plus the loosened Goodreads-specific bar in memory/feedback_goodreads_inclusion.md: textReviewsCount>100 and followersCount>50 are heuristics, not gates. A low-volume reviewer (even 0 followers, 1 review) ships if the text is substantive — real analysis, distinctive framing, multiple paragraphs — or if their self-description signals unusual credibility (named investor, founder, professional in a relevant field).

DEPTH ALONE CAN CARRY A REVIEW (Eric, 2026-10-19). A review that is analytically engaged but carries no sentence of praise still ships when the engagement is real: applied to a concrete domain, naming real cases, taking the argument somewhere. Spending 2,600 words extending the argument is a stronger signal of regard than "highly recommend". Mabel's constellation review was skipped twice on a "positive AND insightful" rule I had written from that very case — circular reasoning dressed as policy — and Eric reversed it. The blockquote can be the reviewer's own reasoning rather than a compliment. See memory/feedback_depth_is_endorsement.md.

What still fails: thin "highly recommend"-class praise with no substance, reviews that are mostly verbatim quotes of Eric, and anything critical or mixed — the site tracks momentum. A 5-star rating does not override mixed text: judge the words, not the stars. On 2026-10-12 a 982-review 5-star reviewer was skipped because the text carried two real criticisms.

Verify any named concept before attributing it to the book. "Governance fortress", "surrogation", "emergent intelligence" and "constellation" all check out as Eric's vocabulary; "mission gravity" and "the ratchet" were reader coinages. Grep data/archive/source-texts/ and data/archive/transcripts/ first.

For each new review not already in content/entries/:
- source_url = the specific review URL from the actor's `shelving.webUrl` field. The actor's `id` is a kca:// content-analytics id, not the review number. Lint now hard-fails a fabricated or placeholder source_url — never invent one to complete a batch.
- type=review, scanner_source="social-scan" (the schema permits only [web-search, social-scan, manual, rss] — "goodreads-scan" fails lint).
- verified:false, because Goodreads is JS-rendered and verify-quotes cannot see it.
- Title format: do NOT prefix with "Goodreads reviewer X —". The title is just the strongest pull quote in single quotes, capped at 200 characters; explain who the reviewer is in the summary and attribution fields.
- Sidebar flags per memory/feedback_sidebar_flags.md. Note that lint forbids sidebar_quote and highlight on type=reaction entries, and HIGHLIGHT_ELIGIBLE_ENDORSERS gates the highlight flag — a Goodreads reviewer will almost never be on it.

Amazon review-count milestones (memory/feedback_amazon_review_milestones.md): ship one flat entry at 500 and 1000. The 2026-10-05 snapshot had 262 Amazon ratings and 406 Goodreads ratings, so 500 is still some way off; no action unless a snapshot crosses it. That snapshot is the most recent — the Amazon rank cron is paused at Eric's direction, so do not expect fresher numbers unless he asks for it back.

Then backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 4. LinkedIn comment archive — `47 10 * * 1,3,5`

```
LinkedIn comment archive scan. Pull Eric's LinkedIn author feed plus the Incorruptible keyword search WITH comments enabled, and archive short superlatives to data/archive/linkedin-comments/ (gitignored). This job does NOT ship anything to the site.

Use waitSecs:0 for both Apify calls, then curl the datasets (docs/SCAN-PROTOCOL.md section 1).

COST CAP — this job was 50% of all Apify volume Oct 10-14 and ships nothing, which is why it moved to 3x/week on 2026-10-14. maxPosts is NOT honoured by the actor (30 was passed, 130 returned). Pass callOptions {"maxItems": 40} on BOTH calls. Both queries use postedLimit "week", so running 3x/week still sees every comment — just up to two days later.

CHECK WHETHER THE CAP COST ANYTHING, and say so either way. Compare the oldest post in this pull against the oldest in the previous run's archive file. On 2026-10-16 the author feed hit the cap and it cost nothing — the previous run already reached past the oldest item returned. On 2026-10-19 the keyword run hit the cap and DID leave a hole: it truncated to Oct 18 onward while the Oct 16 run reached only to Oct 14, so Oct 17 keyword-post comments were never covered. Report the hole rather than silently raising the cap; this lane is archive-only, so a one-day gap is usually not worth extra spend.

1. harvestapi/linkedin-post-search — Eric's author feed, callOptions {"maxItems": 40}:
   {"authorUrls": ["https://www.linkedin.com/in/eries/"], "postedLimit": "week", "maxPosts": 30, "sortBy": "date", "scrapeComments": true, "commentsPostedLimit": "week", "maxComments": 30, "postNestedComments": true}
2. harvestapi/linkedin-post-search — keyword, callOptions {"maxItems": 40}:
   {"searchQueries": ["Incorruptible Ries"], "postedLimit": "week", "maxPosts": 40, "sortBy": "date", "scrapeComments": true, "commentsPostedLimit": "week", "maxComments": 30, "postNestedComments": true}

Save each raw dataset to data/archive/linkedin-raw/<YYYY-MM-DD>-<name>.json, then:

Pass 1 — emit queue:
  python3 scripts/archive-linkedin-superlatives.py /tmp/eries-feed.json --scan-source=linkedin-author-eries
  python3 scripts/archive-linkedin-superlatives.py /tmp/kw-feed.json --scan-source=linkedin-keyword

Pass 2 — classify in-turn, no external API. Read .llm-queue.json and judge each candidate. Filter to kind=comment and drop identifiers already present in data/archive/linkedin-comments/*.json before reading — after a big event the queue runs to 200+ and most are repeats of the same week's items.

KEEP short superlative fragments, including one-word ones — per Eric, 2026-10-03: "keep comments in the archive like 'astounding' (just that one word is enough, we dont need the rest for things like movie posters), same with 'worthy path toward building bigger' and 'this is amazing' kind of stuff." Set pull_quote to JUST the superlative fragment, not the surrounding sentence. These qualify even when the rest of the comment is a question, or when the praise is addressed to the poster rather than the book. See memory/feedback_comment_archive_fragments.md.

A person whose POST was skipped can still have a keepable COMMENT — different lanes. Ed Magee's Oct 18 post was the textbook one-clause skip; his Oct 19 comment, "Eric's talk is still occupying mindspace, rent free", was a clean keep.

SKIP: congratulations ("Congrats!!!!"), purchase notes ("$1.99 on my kindle, purchased!"), lukewarm interest ("looks intriguing"), praise aimed at something other than the book or the talk, commenters who say they have not read it yet, and AI-slop comments. The slop signature is a long fluent sentence restating the post's own thesis back at it — "This is exactly the board governance and mission protection conversation most directors needed to see"; several arrive per event, sometimes with HTML-escape artifacts like "Melissa#39;s". A reading-list post draws a cluster of "got to check them out!" replies — all haven't-read-it skips.

The archive holds COMMENTS only — every record to date is item_kind "comment". The queue also surfaces posts; skip those. But a comment can still yield a CONTENT-side find worth acting on: on 2026-10-19 Ash Wallington posted her article URL in comments, which completed an entry shipped the day before when the link was unreachable.

CRITICAL: when a candidate's relevance depends on the PARENT post, print the parent post IN FULL before deciding. A lowercase or adjectival "incorruptible" near the top of a post is a reason to keep reading, not to dismiss — people routinely use the word casually and credit the book further down. This is how the Paige Kaye entry was nearly lost (memory/feedback_read_whole_parent_post.md).

For each YES write a verdict to /tmp/verdicts-<YYYY-MM-DD>.json with: identifier, kind, source_scan, text, pull_quote, permalink, posted_at, reactions, comments_count, author, parent_post — copied from the queue entry; only pull_quote needs judgment. Then:
  python3 scripts/archive-linkedin-superlatives.py --apply-verdicts /tmp/verdicts-<YYYY-MM-DD>.json
  python3 scripts/generate-comment-cards.py

Report: posts and comments scanned per source, each verified item as one line of "who + quote", the running total across all daily files, and the below-bar candidates with reasons. "No new superlatives this cycle" is fine on a quiet day.
```

## 5. Weekly LinkedIn recall audit — `17 11 * * 0`

```
Weekly LinkedIn recall audit. Check the production scan query for drift against alternates, per memory/feedback_linkedin_query_calibration.md.

Run all three over the same 7-day window, each with waitSecs:0 then scan-triage.py (docs/SCAN-PROTOCOL.md section 1). postedLimit accepts only [any,1h,24h,week,month,3months,6months,year] — "7d" fails validation.

1. PRODUCTION: searchQueries=["Incorruptible Ries"], postedLimit="week", maxPosts=100, sortBy="date"
2. ALTERNATE:  searchQueries=["Eric Ries Incorruptible"], same params
3. BARE:       searchQueries=["Incorruptible"], same params

maxPosts MUST be 100, not 40, and pass callOptions {"maxItems": 100} on each — maxPosts alone is a soft target the actor does not honour. On 2026-09-27 both queries hit the 40 cap, so the comparison was between two truncated lists and reported false agreement — that is how a Raj Sisodia endorsement went unseen for a week. Check and report whether any query hit the cap; if one did, its result is not a valid comparison input. This is the one job where 100 is justified: the comparison is worthless on truncated lists, and this audit is the designed backstop for everything the daily scans miss.

The bare query is noisy (Bible verses, political theory, films, and lowercase adjectival use). Filter it for book relevance before comparing: the post body should mention Eric Ries, Lean Startup, financial gravity, or mission-lock. But note the structural reason the bare query is not redundant: a post that hashtags Eric's name (#EricRies) never contains "Ries" as a standalone token, so the two-word production query cannot match it at all. That is a mechanism, not noise.

Compare recall, then cross-check against content/entries/ for the past 7 days. Report: each query's count, whether any hit the cap, IDs unique to each alternate (up to 10), any high-signal post that two queries returned but we never shipped, and whether the production query is missing more than 20 percent of relevant posts.

Judge by quality as well as rate. On 2026-10-04 the raw miss rate was only 7 percent, but the single missed post was a peer-tier endorsement from the co-founder of the Conscious Capitalism movement — worth escalating on its own.

Audit BOTH halves — recall and judgment. For every relevant post the production query DID return but we never shipped, check it against the inclusion memories before calling it correctly skipped. On 2026-10-11 recall was healthy (8 percent miss, no cap hits) yet the week's real finding was a judgment miss: Fora Fereydouni (Founder & CEO, Cognitai, 47 likes) sat in an Oct 6 daily list of only 13 items and was passed over, then shipped a week late by the audit. A short daily list is not a reason to skim it. Ship anything the audit confirms was wrongly skipped.

Also audit COVERAGE, not just query shape: run `python3 scripts/scan-coverage.py --days 14` and report any day a daily source produced no archive file. These crons only fire while the REPL is idle, so a closed laptop skips a cycle silently. If a gap is real and still unbackfilled, do one catch-up pull with a derived postedLimit (scan_state.choose_posted_limit) and client-side dedup against data/archive/, then ack_gap it.

If a calibration change is warranted, update memory/feedback_linkedin_query_calibration.md, docs/SCAN-PROTOCOL.md and the affected prompt in docs/CRONS.md, then commit. Otherwise make no commit.
```

## 6. Evening content scan — `3 18 * * *`

```
Evening content scan. Follow docs/SCAN-PROTOCOL.md in the repo for the full standing rules (Apify call pattern, inclusion bar, TikTok blocking rule, entry/image/verify/ship steps, reporting format). Read it first — section 1 now carries hard billing caps and the derived-window rule.

Derive the window, do not hardcode it (scan_state): postedLimit = choose_posted_limit(read_watermark(src), now). record_run() each dataset id at launch; clear_run() + write_watermark() after the archive is written. A widened window always needs dedup against data/archive/.

Sources this cycle — run each with waitSecs:0, then scan-triage.py per the protocol:
1. TikTok profile (clockworks/tiktok-profile-scraper, profiles=["ericriesactual"], resultsPerPage=10) — ONLY on Mon/Wed/Fri. On other days skip it entirely and say so in one line. Nothing has shipped from TikTok in three weeks; it is podcast promo cuts, denylisted AI slop, and Eric's own event announcements. When you do run it, the blocking rule applies to every video without exception: grep the id against data/ai-tiktok-denylist.json AND confirm Eric is on camera. If you cannot confirm on-camera, skip. Genuine on-camera clips still get skipped when they are promo cuts of an episode already on the timeline — check before writing an entry.
2. LinkedIn @-mentions (harvestapi/linkedin-post-search, mentioningMember=["https://www.linkedin.com/in/eries/"], maxPosts=40, sortBy="date", callOptions {"maxItems": 25}).
3. Twitter/X @-mentions (apidojo/tweet-scraper, searchTerms=["@ericries"], maxItems=20).

When an event Eric spoke at has just happened, check whether the organiser has published a post-event quote. The NACD entry carried only its pre-event agenda blurb until NACD's own account published what he actually said; swapping that in, moving the summary to past tense and dropping the "upcoming" tag is a real upgrade worth doing the morning after any major event.

Reactions have NO numeric ceiling (Eric, 2026-10-14: "relax the five reactions ceiling from now on, if quality is high"). Quality is the only gate — if the single argument against shipping a reaction is that the parent already has N, ship it. Still skip the "great event!" class, which has two recurring shapes: a name-list where Eric is one of several speakers, and a post that gives him one clause before moving to a different session for its real takeaway (David Buck, 2026-10-17, is the textbook case).

But do NOT confuse that with a field observation. A credible practitioner reporting that the ideas are SPREADING — "more and more builders choosing public benefit missions" (Peter Ward, ex-Oura, 2026-10-17, which Eric reversed my skip on) — ships even as one paragraph inside an otherwise off-topic post with low engagement. Adoption evidence from someone with standing to see it is a category the timeline is short of, and the host post's topic is a weak signal against it. The test is whether the paragraph asserts something about the world or merely nods at the book. See memory/feedback_field_observations_ship.md.

A promotional company post is often better used to ENRICH the parent entry than shipped as its own: SEEK Alabama's booth post documented that Innovate Alabama sponsored the Inc. 5000 book signing, which belonged in source_urls on the event, not on the timeline.

Also: pick 2-3 unimaged older entries from the backlog and source photos. Query with BOTH image and attribution_image null. THIS SEAM IS DRY as of 2026-10-17 — YouTube thumbnails exhausted, LinkedIn archive avatars give zero matches for the old entries, Luma has no og:image, the rest is paywalled or small orgs. Say "no new image found" rather than forcing a weak one. Org and event logos go in /images/events/ — there is no /images/orgs/. Reject og:images that are grids of other people's faces.

Finish with backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 7. Sidebar curation — `27 19 * * *`

```
Sidebar curation. Re-evaluate the past 30 days of content/entries/ and decide the top 8 entries carrying type_metadata.featured (the "What's New" rail).

Criteria per memory/feedback_sidebar_flags.md and memory/feedback_highlights_row_grows.md:

WHAT'S NEW (featured, exactly 8) — third-party momentum only: events, endorsements, real news. Prefer upcoming book-tour events, heavyweight endorsements, podcast appearances, viral coverage. Rotate an event out the day after it happens. Eric's own posts are auto-excluded by the index filter (isSelfAmplification keys off both the speaker and the venue), so do not bother flagging them — an entry sourced to Eric's own LinkedIn or TikTok will never render here no matter what flag it carries.

Only standalone types have ever been featured — endorsement, event, podcast, media, milestone. A type=reaction is a child of its parent and is not a candidate, however high its engagement: Christopher O.H. Williams at 57 reactions on 2026-10-19 was the highest-engagement post of the NACD wave and still was not eligible.

Be conservative. Churn the featured set only for a clearly better candidate; a single swap is a normal night's work and no change at all is a fine outcome. When an event is rotating out tomorrow anyway, do not also churn a second slot tonight — one change at a time.

Tiebreakers that have actually decided calls:
- Composition. On 2026-10-16 the rail held three events, two media, two endorsements and zero podcasts, which is what sent a 15-day-old milestone out for a 38K-subscriber interview.
- Reach, as a reason NOT to swap: a 1,570-subscriber podcast does not displace a 38,400-subscriber one just for being newer.
- Quote strength over freshness. On 2026-10-18 Kim Scott — allowlisted heavyweight, same day — did not displace Alistair Croll, because "such an important book!" appended to a reshare is thinner than Croll giving away a dozen copies and calling it "an incredibly important reset for startups and capitalism itself".

EVENT PIPELINE — answered, do not flag nightly. A targeted search on 2026-10-20 found no unscheduled dates; the tour is concluding by design and SOSV on Nov 4 is the last event. Raise it once when that slot empties, then stop. The rail will keep working as a momentum surface — the scan produced eleven standalone entries in the six days to Oct 19 — it just stops answering "where to see Eric next". See memory/project_event_pipeline_winding_down.md.

HIGHLIGHTS (highlight) — GROWS, NEVER TRIMMED. Lint enforces a floor. Only ADD; never remove a highlight flag from any entry, including ones dropping out of What's New. The name must already be on HIGHLIGHT_ELIGIBLE_ENDORSERS in scripts/lint-entries.ts. Adding a new name is Eric's editorial call — ship such an entry with type_metadata.sidebar_quote instead and ask via AskUserQuestion, never in prose. The operative distinction is author tier versus CEO tier: a named author with a body of work (Steve Blank, Nir Eyal, Rory Sutherland, Raj Sisodia) is worth asking about; the CEO of a notable company is not, however on-thesis the endorsement (memory/feedback_highlights_row.md). Academic-publication credentials (a Springer monograph, a lectureship) are not the same as that body-of-work recognition, and neither is one leadership title alongside a board career — do not ask on those.

"Only ADD" does not mean add every eligible instance. Kim Scott is allowlisted and already carries three faces in the row; her 2026-10-18 one-liner was deliberately left unflagged because a fourth identical face with a weaker quote makes the row repetitive, not stronger. Declining to add is not trimming — the floor stays put.

Note: lint forbids sidebar_quote and highlight on type=reaction entries — those flags belong on the parent.

Format a highlight as "Name: 'verbatim short quote'".

Use Edit to MERGE flags into the existing type_metadata object, never overwrite it.

Then verify, in this order:
  npx tsx scripts/lint-entries.ts
  npm run build
  grep the rendered dist/index.html to confirm the change actually reached the DOM
Do not trust the JSON alone — twice, edits landed in a component that produces no output (memory/feedback_verify_in_dom.md). Confirm both that the new entry appears in What's New and that the Highlights carousel face count did not drop.

Then commit and push. If nothing changed, make no commit and say so. Set PATH="/opt/homebrew/opt/node@23/bin:$PATH" before npm/npx commands.
```

---

## Cadence history

- **2026-06-01** — pruned 4 launch-week extras returning zero net new finds: midday scan, afternoon Goodreads, late-evening mention scan, morning Amazon rank.
- **2026-06-25** — Goodreads daily → Mondays only; Amazon rank daily → Mondays + Thursdays.
- **2026-08-23** — added the weekly recall audit after discovering the 3-word query was missing most relevant posts.
- **2026-08-31** — Amazon rank paused indefinitely.
- **2026-10-14** — Apify hit 50% of its $29/month limit. Added hard `callOptions.maxItems`
  caps (maxPosts is not honoured: 30 requested, 130 returned), moved the comment
  archive to Mon/Wed/Fri, and made the TikTok pull Mon/Wed/Fri inside the evening
  scan. The comment archive was 50% of all Apify volume and ships nothing to the
  site. Eric's call on cadence; caps applied first.
- **2026-10-20** — watchdog moved 8:37 → 8:17. Twice in two days the watchdog
  turn consumed the 9:07 morning-scan slot: on the 19th by doing slow work before
  the rolls, on the 20th by simply running long (8:37 → 9:14) — a cron cannot fire
  while a turn is in progress, so correct ordering alone was not enough. Fifty
  minutes of headroom plus a hard "do not start work that could run past 9:00"
  rule in the prompt.
- **2026-10-04** — standing rules extracted to `SCAN-PROTOCOL.md`; prompts shortened to pointers; watchdog given rolling self-renewal; these specs moved into the repo so they survive a platform change.

If volume picks up again (a major TV hit, paperback release, viral moment), the
pruned midday and late-evening scans can be restored from `git log` around
2026-04-25, which set up the original launch-week schedule.
