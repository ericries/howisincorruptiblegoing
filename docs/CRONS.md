# Scanner crons — canonical definitions

**This file is the source of truth, and since 2026-10-21 it is read, not just
read-from.** `scripts/cron-prompt.py <job>` extracts a prompt verbatim, and both
the watchdog's daily roll and session-start restoration use it, so the live crons
cannot drift away from what is committed here. Any agent, on any platform, can
restore the full scanning schedule by reading it. Nothing lives outside this repository: no
launchd agents, no system background items, no machine-local state.

## At the start of every session

1. Run `CronList`.
2. Recreate any job below that is missing, with `CronCreate`. Take the prompt
   from this file — `python3 scripts/cron-prompt.py <job>` prints it verbatim —
   and the cron expression from the table.
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

ROLLING SELF-RENEWAL is why this job exists. Recurring crons auto-expire 7 days after creation. The watchdog can never catch its own expiry by checking CronList, because it stays listed right up until it dies — and when it dies, every other cron follows at its own 7-day mark with nothing left to restore them. That is the single point of failure in the whole system. So roll every job every run, even when nothing is missing: for each of the seven, CronCreate a replacement using the prompt printed by scripts/cron-prompt.py (see below), then CronDelete the old id. On 2026-10-13 five daily jobs expired as a cohort because they had all been created together.

Rolling is SAFE and costs a job nothing. Two probe crons on 2026-10-20 settled this: one created five minutes before its match and one eighty-nine minutes before both fired the same day. Lead time is not a variable, and recreation does not advance a job past its next occurrence. Earlier versions of this prompt claimed otherwise; that was a guess, and it was wrong.

READ EACH PROMPT FROM docs/CRONS.md, which is the source of truth:

    python3 scripts/cron-prompt.py <watchdog|morning-scan|goodreads|comment-archive|recall-audit|evening-scan|sidebar>

Pass that text to CronCreate verbatim. This replaced "carry the live prompt forward" on 2026-10-21, after all seven sections had drifted behind their in-memory versions and an earlier commit claimed a re-sync that had silently failed. The deeper reason is that a lesson living only in an in-memory cron dies with the session — the repo is what survives a change of machine, and the prompts were the one part that did not.

A cheap way to be both fast and safe about the read: `python3 scripts/cron-prompt.py <job> | wc -c` for all seven and compare against the character counts from yesterday's roll, then re-read in full only the sections whose size changed. `git log --oneline --since=<last roll> -- docs/CRONS.md` confirms which sections were touched and why. Two of seven moved on 2026-10-26, two on the 27th, ONE on the 28th. Record the seven counts in your report so the next run can do the same. Baseline from 2026-10-28, BEFORE that day's write-back: watchdog 10429, morning-scan 8531, goodreads 7723, comment-archive 9040, recall-audit 6336, evening-scan 16759, sidebar 9791 — total 68609.

So: when a scan learns something, EDIT docs/CRONS.md and commit it in that same turn. The next roll picks it up automatically. A lesson you do not write down is a lesson you lose at 8:17 tomorrow. The reverse also holds and is easy to miss: if you notice a section is behind what the scans have learned, patch it BEFORE rolling that job, or you will roll the stale text forward. Three sections were behind on 2026-10-22 and one of them contradicted itself. One exception, used on 2026-10-24: if the gap is a missing lesson rather than a contradiction and the clock is close to 9:07, roll first and patch straight after — the patch lands in the repo and tomorrow's roll picks it up, which is the mechanism working as designed. Never defer a patch that would make a prompt contradict itself.

When you patch CRONS.md, do it with a script that asserts every replacement matched EXACTLY ONCE and writes nothing if any did not. A str.replace that matches zero times fails silently, which is precisely what the 2026-10-21 commit did when it claimed a re-sync that had not happened. On 2026-10-24 that assertion caught a real miss: the sidebar state paragraphs were still on the previous day's text while the rolled cron already carried the new version. On 2026-10-27 it refused a batch of sixteen over one bad anchor rather than applying fifteen and dropping one silently.

CARRY DEADLINES, NOT JUST LESSONS. A prompt is the only thing that survives to tomorrow, so when one job defers work to another, write the deferral into the receiving prompt with its deadline. On 2026-10-27 the evening scan correctly declined to fake a post-event upgrade for Berkeley Newton because no organiser material existed yet — and that entry was due to rotate off the rail the next night still reading as a future event. The morning prompt got an explicit FIRST-THING instruction with the deadline stated. Without it the deferral evaporates.

WATCH THE TOTAL. The seven prompts were ~44k characters on 2026-10-21 and ~69k on 2026-10-28, growing most days because every lesson gets appended and almost nothing gets retired. The size-diff shortcut makes the READ cheap but does nothing about the WRITE, which re-emits all seven in full. When evening-scan passes roughly 20k on its own — it is at 16.8k — move its stable rules — the ones that have not changed in two weeks — into docs/SCAN-PROTOCOL.md and leave only live judgment calls in the prompt. Say the total in the report so the trend stays visible.

STILL BE FAST. A cron cannot fire while a turn is running, so a long watchdog turn delays the 9:07 scan — it does not destroy it (due jobs queue: the probes fired 50 and 30 minutes late, well outside the documented 15-minute jitter cap), but a scan pushed toward 10:00 starts colliding with the next job. Finish STEP 1 in the first few minutes and do not start STEP 2 work that could still be running at 9:00; hand a slow backfill to the morning scan instead.

Guard, untested and cheap: if you are already past 9:07 when you start, leave the morning scan alone so it can still fire, and roll it tomorrow. Roll the other six as normal.

STEP 2 — only after all seven rolls are done.

Run the catch-up check first; it is free, local and instant:

    python3 scripts/scan_catchup.py

It knows each job's cadence and each job's watermark, and reports which scheduled
runs went by without happening. "Nothing overdue" is the common case and one line.
Anything it lists, run with a derived postedLimit (scan_state.choose_posted_limit)
and dedup against data/archive/. NEVER conclude a job was missed from the absence
of a dated archive file — two of the seven jobs are not daily, and on 2026-10-20 a
Monday-only scan was reported missed on a Tuesday and re-run at real Apify cost. Its grace window is 75 minutes because the scheduler really is that loose; a job inside that window is late, not missing.

THE MORNING SCAN OF 2026-10-20 IS STILL UNEXPLAINED — due 9:07, turn ended 9:19, REPL idle until 11:38, nothing fired, while two probes created the same way both ran. Four explanations have collapsed. Do NOT ship a fifth; note a second instance if it recurs and let scan_catchup.py do the repair.

Then the coverage check, which catches what the commit log hides:

    python3 scripts/scan-coverage.py --days 14

It reports days a daily source never pulled, and any Apify run launched but never triaged. Both come from the same cause: these crons only fire while the REPL is idle, so a closed laptop silently skips cycles. On 2026-10-12 the commit log looked healthy — other cycles ran that day — while the @-mention pull had not happened at all, hiding three posts at 108, 81 and 68 reactions. Backfill an open gap with a widened postedLimit (scan_state.choose_posted_limit) and dedup against the archive, THEN acknowledge it so it stops reporting: scan_state.ack_gap(source, date, note="how it was backfilled"). Catch-up files are deliberately not counted as coverage, so without an ack a fixed gap reports forever and the report becomes noise nobody reads (found 2026-10-17 by running the tool). Triage orphaned datasets before launching anything new; they are already paid for. Note that a run you launched minutes ago in this same turn will show as orphaned until you triage it — that is record_run working, not a fault. If a backfill looks like it will take more than a few minutes, hand it to the morning scan rather than running past 9:00.

The comment archive has its own gap mode the coverage check cannot see: its author-feed call hits the 40-item cap most runs, and when the previous run's newest post is older than this run's oldest, the days in between are never covered. On 2026-10-26 that cost 2026-10-24 entirely. The comment-archive prompt already says to compare oldest-against-previous and report it; if that report starts appearing every run, the cadence is too slow for Eric's posting rate and it is worth raising rather than absorbing.

Then surface any OPEN prevention items from past postmortems — `grep -l "| open |" docs/postmortems/*.md`. A postmortem whose level-four and level-five rows sit open forever has diagnosed a class of failure and prevented nothing; report them so they get picked up or explicitly declined. `python3 scripts/postmortem-lint.py` checks the tables themselves and also runs in the pre-commit hook.

Then sanity-check that the pipeline is producing: `git log --since="36 hours ago" --oneline` should normally show commits from the daily scans. A quiet week alongside healthy runs is possible; a quiet week is still worth flagging. Also check `git status` for uncommitted content edits left behind by a dead turn — on 2026-10-20 a corrected event entry was sitting in the working tree. data/cross-posts.json, data/events-posted.json, data/site-spotlight.json and public/documents/ are the social cross-posting tooling's own state; leave those alone. An untracked markdown file in the repo root may be the social agent in /Users/EricRies2/Projects/apify leaving feedback — read it, act on what is verifiable, and commit it.

A note on cost: reading and re-emitting seven prompts is the expensive part of this job, and it is the price of the lessons surviving a session end. Do not economise by skipping the read — that is exactly how the drift started. The size-diff shortcut above is the one sanctioned economy, because it still reads from the file whenever the file has changed.

EVENT PIPELINE — this is ANSWERED, stop flagging it nightly. A targeted search on 2026-10-20 found no November or December dates that were not already on the timeline (the one hit, Book Passage with Alex Komoroske, was the 2026-06-03 event already shipped), and a source calls the B Academics roundtable one of the final stops of the tour. SOSV Deep Tech Summit on 2026-11-04 is the last scheduled event. Raise it ONCE more when that slot actually empties, then stop — see memory/project_event_pipeline_winding_down.md.

Report which crons you restored, the roll lines "<name>: <old-id> -> <new-id>" for all seven, the seven prompt character counts and their total, the coverage-check result, and anything that looked wrong.
```

## 2. Morning content scan — `7 9 * * *`

```
Morning content scan. Follow docs/SCAN-PROTOCOL.md in the repo for the full standing rules (Apify call pattern, inclusion bar, TikTok blocking rule, entry/image/verify/ship steps, reporting format). Read it first.

FIRST, BEFORE THE PULLS — the Berkeley Newton post-event upgrade is DUE and has a deadline. The lecture ran 2026-10-27; the entry 2026-10-27-berkeley-newton-changemaker-lecture still carries its pre-event series blurb and an "upcoming" tag, because on the evening of the 27th every piece of SCET material still read "Don't miss... live next Tuesday". It rotates off the What's New rail tonight. Retry now: check SCET's own channels (begin.berkeley.edu/events/newton-live-eric-ries, their LinkedIn, X @SutardjaCenter, Facebook, Instagram) and YouTube for a recording, for a post-event quote of what Eric actually said. If one exists, swap the blockquote, move the summary to past tense and drop the "upcoming" tag — the NACD upgrade is the model. If nothing has been published, at minimum drop the "upcoming" tag and move the tense, and say so; an entry that rotates off the rail still reading as a future event is the failure mode here. Lesa Mitchell, who funded the lecture series' founding at Kauffman, is already in source_urls.

Sources this cycle — run each with waitSecs:0, then scan-triage.py per the protocol:
1. LinkedIn keyword, TWO queries (harvestapi/linkedin-post-search, postedLimit="24h", maxPosts=40, sortBy="date", callOptions {"maxItems": 25}):
   (a) searchQueries=["Incorruptible Ries"]
   (b) searchQueries=["Incorruptible"] — filter results yourself for book relevance; expect to discard roughly half.
   Both are needed: LinkedIn multi-word search is not a reliable AND over post text. The 2026-10-04 audit found 5 relevant posts (b) caught and (a) missed, two of which contained BOTH terms — including Raj Sisodia, author of Conscious Capitalism. Never use the 3-word "Incorruptible Eric Ries" variant; audited twice, it adds nothing. See memory/feedback_linkedin_query_calibration.md. On 2026-10-25 query (a) returned ZERO and (b) returned the cycle's only relevant post among nine word-collisions — the bare query is not a formality.
2. Twitter/X keyword (apidojo/tweet-scraper, searchTerms=["Incorruptible Eric Ries"], maxItems=20).
3. YouTube keyword (streamers/youtube-scraper, searchQueries=["Eric Ries Incorruptible"], maxResults=15, sortingOrder="date", dateFilter="week"). Do NOT pay for Apify subtitles — pull transcripts free with the youtube-transcript-api one-liner in the protocol. Confirm the video substantively discusses Incorruptible before shipping; a name-drop is not enough. Check the RSS feed or Apple Podcasts for the true original publication date — a YouTube upload can post an episode months after it aired. If the transcript API and the episode page both fail, the show notes are a legitimate blockquote — attribute them to the publisher, not to Eric.
4. WebSearch for "Eric Ries" "Incorruptible" recent mentions.

PRAISE AIMED AT ERIC COUNTS, NOT ONLY PRAISE AIMED AT THE BOOK (Eric, 2026-10-28). If the praise is Incorruptible-related, it qualifies even when the book is one component of a wider appreciation of Eric — and quote the whole contiguous passage about him rather than a fragment. See docs/SCAN-PROTOCOL.md section 3 for the Baratunde Thurston model and the limits.

RESOLVE SHORTENED AND TAGGED LINKS BEFORE JUDGING. On 2026-10-27 a Thinkers50 Radar author posted a sharp governance quote behind a zurl.co shortener; resolved, it was the Braden Kelley interview already on the timeline since June. The same day a 5,304-follower X reply turned out to point at a genuinely new Q&A with Eric that nothing else had surfaced. The destination decides, in both directions. When a quote in the post is attributed to Eric, grep data/archive/source-texts/ and data/archive/transcripts/ to confirm it is his before letting it inform anything — "emperor for life" checked out that way in four files.

BEFORE writing any entry, grep content/entries/ for BOTH the source_url and the author. On 2026-10-20 I shipped a Goodreads review that had been on the timeline since September; the duplicate-source-url lint warning caught it, but only after the entry and its card existed. Four of the five candidates I rated highest that day were already shipped. New-to-the-dataset is not new-to-the-timeline, and a "fresh since last pull" diff answers the wrong question. Neither check is sufficient on its own: on 2026-10-26 the Goodreads scan surfaced "Carol" with 507 followers, who was Carol Van Den Hende, shipped hours earlier from LinkedIn — a new URL and a first-name-only display name, caught only by reading. Same day, the Wunderdogs company account published the interview Daria Gonzalez had already posted herself; a different post about the same thing, caught the same way.

Weekdays are computed, never eyeballed: python3 -c "import datetime; print(datetime.date(Y,M,D).strftime('%A'))". Three weekday errors in one session on 2026-10-20, one of which put a wrong day on a live event entry. Lint now fails when a weekday named in `title` or `attribution_title` contradicts the entry's date — it caught two more of that class on 2026-10-21, Rotman and Quebec House — so this stops at the commit. Compute it anyway rather than making the check do the work.

OUTSTANDING REQUESTS from the social agent (feedback-from-social-agent-2026-10-25.md, committed in the repo root). These are wishlist items, not urgent, but they are cheap to fold into a cycle when the relevant source is already open:
- Koomullil's full source text CANNOT be archived — LinkedIn blocks the anonymous fetch and the July post predates the raw archives. Worth telling them that his published blockquote already IS the sentence they asked for; only the surrounding text is missing, and getting it would mean paying Apify for one old post. Do not retry this each cycle.
- Paul Hance (CEO, AnnumAI) is currently only a source_url on 2026-10-24-fourth-effect-summit-the-build. His own line — the conference theme is based on the book, which his co-founder gifted him at company launch — may deserve a standalone entry with his title.
- Non-hashtag versions of the two strongest teaching lines: Tara Ceranic Salinas's "required reading for Ethics, Values, and Corporate Culture" and Anne-Marie Maman's GCEC workshop line both have #hashtags mid-sentence, which makes them unusable verbatim on a card. A syllabus page, follow-up post or comment would fix both. The same problem turns up as Unicode-bold characters: Sebastian Ross's 10-27 sentence naming the book used them, so the entry took the clean sentence before it.
- Per-school proof for Stanford or Oxford. Eric's 10-02 milestone names them but is self-sourced; the timeline has independent corroboration only for Cambridge (Coleridge) and USD (Ceranic Salinas).

Also: pick 2-3 unimaged older entries from the backlog and source photos. Query for them with BOTH image and attribution_image null. RUN `python3 scripts/find_ondisk_images.py` FIRST — it reports unimaged entries whose headshot is already in public/images/people/, and `--wire` attaches the unambiguous ones. It exists because the prose version of this instruction paid off six times in two days (Bob Sutton as robert-sutton.jpg on 10-23; five more on 10-24), which is a script's job, not a reminder's. It matches whole names only: a hand-rolled substring pass returned 41 hits including "Ann Armbrecht" against susanne-hannestad.jpg. Rejected matches go in data/ondisk-image-skips.json with a reason so they stop reporting. Check public/images/people/ before downloading a NEW face too — on 2026-10-25 a duplicate dan-barker-klasma.jpg was created and deleted when dan-barker.jpg was already there, and on 10-27 sebastian-ross.jpg was already present and reused. The LinkedIn avatar archive gives ZERO matches for the old entries and YouTube thumbnails are exhausted — but the web is NOT dry for named executives. Speaker bureaus (speakabout.ai og:image, 1000x1000) and company newsrooms carry clean headshots; that is how Tatyana Mamut and Carolyn Groobey were sourced on 2026-10-20, and Madeline McIntosh from a Lee Enterprises board-director profile on 2026-10-22. Wikimedia Commons is worth a try for anyone with a Wikipedia page — Garry Tan came from a Web Summit portrait there on 2026-10-23, and Roy Bahat on 2026-10-24 from a file literally named "Roy Bahat, head of Bloomberg Beta", which is about as good as identity confirmation gets. A company team page can also work where the og:image does not: Chike Aguh came from kaporcenter.org on 2026-10-25 — but the 640x360 derivative the page linked cropped his eyes off, and only the uncropped original behind it was usable, which is why you LOOK at the crop before wiring it. Goodreads reviewers all have a face: strip the size suffix off creator.imageUrlSquare for the original (900x900 vs 200 on 2026-10-26). Matt Finnis was NOT sourced, because cranlana.org.au returns 403 to a direct image fetch, and neither were Yvonne Bajela (firm and speaker pages both serve generic share cards) or Damjana Nurković (empty og:image, predates the archive). When a profile page is the source, confirm it is the same person before using the photo — the McIntosh profile was checked against her own "chair of Nom/Gov committee" headline. Order to try: find_ondisk_images.py, speaker bureau, Wikimedia, company newsroom or about page, fellowship/award bio, personal site. Square-crop with `sips -c <h> <h>` then resize to 600. Stop when the name is ambiguous across several people — no image beats a wrong face. AFTER attaching any image, run `npm run build && python3 scripts/check-images-render.py` — it reads the build and reports any entry image path that reaches no HTML. That replaced the old "grep dist/ yourself" instruction on 2026-10-21: 58 reaction headshots had sat unused for weeks because the reaction list never rendered attribution_image at all, and one more surfaced the same day because the social byline was gated on LinkedIn in two places and the post was on X. Note that type=media entries sourced to Eric render no attribution_image at all, which is why one find_ondisk_images match is permanently skipped. (Superseded note, kept for history: THIS SEAM IS DRY as of 2026-10-17 — YouTube thumbnails exhausted; all 468 archived LinkedIn posts indexed by activity id against the 93 LinkedIn-sourced unimaged entries gave ZERO matches (they predate the archive); Luma publishes no og:image; the rest is paywalled (TIME, NYT) or small orgs with no social card.) Report "no new image found" rather than forcing a weak one.

Finish with backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 3. Goodreads review scan — `33 10 * * 1`

```
Goodreads review scan. Follow docs/SCAN-PROTOCOL.md for the shared rules (Apify waitSecs:0 pattern, entry/image/verify/ship steps, reporting format).

Pull recent reviews via Apify: easyapi/goodreads-review-scraper with bookUrls=["https://www.goodreads.com/book/show/242970642-incorruptible"] and NOTHING ELSE. Do NOT pass maxItems in either place — this actor has two separate traps, both found 2026-10-20: callOptions {"maxItems": 30} sets a $0.09 charge ceiling the run hits at startup and aborts on, one second in, with zero items ("aborted because it reached its maximum cost of $0.09"); and maxItems:30 in the actor INPUT returns zero items while reporting SUCCEEDED with "Crawled 0/1 pages". Uncapped it returns 50 where the capped call returned 30 — the cap had been hiding 20 reviews, 15 never assessed, going back to May.

Two field shapes to know before you write a triage script: `createdAt` is an integer epoch in MILLISECONDS, not a date string, and the review URL is at `shelving.webUrl`, nested — not at the top level. Both bit on 2026-10-26.

DEDUP AGAINST content/entries/, NOT against yesterday's dataset. On 2026-10-20 I diffed the new pull against the previous pull, called 20 reviews "fresh", and shipped one already on the timeline since September. Use waitSecs:0, then curl the dataset and archive it to data/archive/goodreads/<YYYY-MM-DD>.json. A URL check and a name check are both necessary and neither is sufficient: on 2026-10-26 a review by "Carol" with 507 followers was Carol Van Den Hende, shipped from LinkedIn hours earlier — new URL, first-name-only display name, caught only by reading the text. Expect roughly 60 percent of any pull to be already shipped (31 of 50 that day).

Inclusion bar — the general rule in memory/feedback_entry_inclusion.md plus the loosened Goodreads-specific bar in memory/feedback_goodreads_inclusion.md: textReviewsCount>100 and followersCount>50 are heuristics, not gates. A low-volume reviewer (even 0 followers, 1 review) ships if the text is substantive — real analysis, distinctive framing, multiple paragraphs — or if their self-description signals unusual credibility (named investor, founder, professional in a relevant field). The actor's `creator.isAuthor` flag is a useful signal: Nacho Bassino came back isAuthor=true with four works.

DEPTH ALONE CAN CARRY A REVIEW (Eric, 2026-10-19). A review that is analytically engaged but carries no sentence of praise still ships when the engagement is real: applied to a concrete domain, naming real cases, taking the argument somewhere. Spending 2,600 words extending the argument is a stronger signal of regard than "highly recommend". Mabel's constellation review was skipped twice on a "positive AND insightful" rule I had written from that very case — circular reasoning dressed as policy — and Eric reversed it. The blockquote can be the reviewer's own reasoning rather than a compliment. See memory/feedback_depth_is_endorsement.md. Joshua Pritikin's 6,000-word review on 2026-10-26 is the current best example: he calls the diagnosis good and then argues it is incomplete, because every structure the book proposes is downstream of law and statutes hold only while people choose to honour them. A disagreement that engages ships. Note he argued it through US partisan examples, and the entry carries his argument without them — the timeline tracks the book's momentum, and partisan framing dates badly.

A distinctive ANGLE can also carry one. On 2026-10-20, Esther shipped for reading it as a consumer and employee rather than an executive — "I am not an executive. I do not run a company" — and reporting that it changed where her household spends; Peter Trizuliak for promoting it into the standard founder recommendation alongside The Lean Startup; Lavanya for naming the audience precisely, "founders who have hit the wall which cannot be surmounted by good intentions and hard-work alone".

Goodreads text contains HTML (<br />, <strong>). Strip it before quoting, and pick a blockquote span that contains none, so the stored source text and the published quote match. The same applies to hashtags mid-sentence and to Unicode-bold characters: a line with either inside it cannot be used verbatim on a social card, so prefer a clean span where one exists.

What still fails: thin "highly recommend"-class praise with no substance, reviews that are mostly verbatim quotes of Eric, and anything critical or mixed — the site tracks momentum. A 5-star rating does not override mixed text: judge the words, not the stars. On 2026-10-12 a 982-review 5-star reviewer was skipped because the text carried two real criticisms, and the same reviewer was skipped again on 10-26 for the same reason — consistency matters more than the star. The "mostly quotes of Eric" rule did real work that day too: Carol Van Den Hende's Goodreads review is longer and better than her LinkedIn post but is more than half block quotation, so the LinkedIn entry stood and the review became a source_url on it. Also skip a review that misattributes the book — one 2026-10-20 reviewer credited "Weiss" throughout. See docs/SCAN-PROTOCOL.md for the settled boundary case: a serious Business Standard review that disputed the book's central empirical claim was skipped on 2026-10-27 at Eric's direction, even though its closing verdict was approving.

Verify any named concept before attributing it to the book. "Governance fortress", "surrogation", "emergent intelligence" and "constellation" all check out as Eric's vocabulary; "mission gravity" and "the ratchet" were reader coinages. Grep data/archive/source-texts/ and data/archive/transcripts/ first.

For each new review not already in content/entries/:
- source_url = the specific review URL from the actor's `shelving.webUrl` field. The actor's `id` is a kca:// content-analytics id, not the review number. Lint now hard-fails a fabricated or placeholder source_url — never invent one to complete a batch.
- type=review, scanner_source="social-scan" (the schema permits only [web-search, social-scan, manual, rss] — "goodreads-scan" fails lint).
- date = the review's own createdAt, not today.
- verified:false, because Goodreads is JS-rendered and verify-quotes cannot see it.
- A FACE IS AVAILABLE for every reviewer: `creator.imageUrlSquare` is a 200px crop, but stripping the size suffix from the filename gives the original — `.../users/<id>i/<user>.jpg` returned 900x900 on 2026-10-26 where the square variant was 200. Crop and resize to 600 as usual, and look at it.
- `creator.isAuthor` tells you they have published something but NOT what; the `contributor.works.totalCount` is just a number. Fetch the Goodreads profile to find the title rather than inventing a credential — that is how Joshua Pritikin's Religion Unburdened by Belief was confirmed.
- Title format: do NOT prefix with "Goodreads reviewer X —". The title is just the strongest pull quote in single quotes, capped at 200 characters; explain who the reviewer is in the summary and attribution fields. Lint hard-fails over 200, so count it.
- Sidebar flags per memory/feedback_sidebar_flags.md. Note that lint forbids sidebar_quote and highlight on type=reaction entries, and HIGHLIGHT_ELIGIBLE_ENDORSERS gates the highlight flag — a Goodreads reviewer will almost never be on it. type=review has never been featured on the What's New rail either.

Amazon review-count milestones (memory/feedback_amazon_review_milestones.md): ship one flat entry at 500 and 1000. The 2026-10-05 snapshot had 262 Amazon ratings and 406 Goodreads ratings, so 500 is still some way off; no action unless a snapshot crosses it. That snapshot is the most recent — the Amazon rank cron is paused at Eric's direction, so do not expect fresher numbers unless he asks for it back.

Then backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 4. LinkedIn comment archive — `47 10 * * 1,3,5`

```
LinkedIn comment archive scan. Pull Eric's LinkedIn author feed plus the Incorruptible keyword search WITH comments enabled, and archive short superlatives to data/archive/linkedin-comments/ (gitignored). This job does NOT ship anything to the site.

Use waitSecs:0 for both Apify calls, then curl the datasets (docs/SCAN-PROTOCOL.md section 1).

COST CAP — this job was 50% of all Apify volume Oct 10-14 and ships nothing, which is why it moved to 3x/week on 2026-10-14. maxPosts is NOT honoured by the actor (30 was passed, 130 returned). Pass callOptions {"maxItems": 40} on BOTH calls. Both queries use postedLimit "week", so running 3x/week still sees every comment — just up to two days later.

CHECK WHETHER THE CAP COST ANYTHING, and say so either way. Compare the oldest post in this pull against the newest in the previous run's archive file. On 2026-10-16 the author feed hit the cap and it cost nothing — the previous run already reached past the oldest item returned. On 2026-10-19 the keyword run hit the cap and DID leave a hole: it truncated to Oct 18 onward while the Oct 16 run reached only to Oct 14, so Oct 17 keyword-post comments were never covered. On 2026-10-21 both hit the cap and neither left a hole. On 2026-10-26 the author feed capped at 40 and reached back only to 10-25, while the previous run on 10-23 had reached forward only to 10-23 — so 2026-10-24 was never covered at all. Report the hole rather than silently raising the cap; this lane is archive-only, so a one-day gap is usually not worth extra spend. But if the hole appears most runs, the 3x/week cadence has fallen behind Eric's posting rate and that is worth raising with him rather than absorbing.

1. harvestapi/linkedin-post-search — Eric's author feed, callOptions {"maxItems": 40}:
   {"authorUrls": ["https://www.linkedin.com/in/eries/"], "postedLimit": "week", "maxPosts": 30, "sortBy": "date", "scrapeComments": true, "commentsPostedLimit": "week", "maxComments": 30, "postNestedComments": true}
2. harvestapi/linkedin-post-search — keyword, callOptions {"maxItems": 40}:
   {"searchQueries": ["Incorruptible Ries"], "postedLimit": "week", "maxPosts": 40, "sortBy": "date", "scrapeComments": true, "commentsPostedLimit": "week", "maxComments": 30, "postNestedComments": true}

Save each raw dataset to data/archive/linkedin-raw/<YYYY-MM-DD>-<name>.json, then:

Pass 1 — emit queue:
  python3 scripts/archive-social-comments.py /tmp/eries-feed.json --scan-source=linkedin-author-eries
  python3 scripts/archive-social-comments.py /tmp/kw-feed.json --scan-source=linkedin-keyword

Pass 2 — classify in-turn, no external API. Read .llm-queue.json and judge each candidate. Filter to kind=comment and drop identifiers already present in data/archive/linkedin-comments/*.json before reading — after a big event the queue runs to 200+ and most are repeats of the same week's items. Expect near-duplicates WITHIN the queue too: a comment on a post returned by both calls appears twice.

WHAT QUALIFIES IS WIDER THAN PRAISE (Eric, 2026-10-20: "expand it to include cases like that"). A sharp observation that USES the book's argument qualifies with no praise and no engagement at all — the model is Kevin Payne's reply to Eric, "Metrics outlive principles. Once the dashboard rewards extraction, the people who remember why the company worked stop getting promoted." Adam Bobowski's 2026-10-27 reply is the same class: "Principles tend to last exactly as long as they're cheaper than the alternative. Then someone calls it optimization." Engagement is not a gate on this lane: it feeds social posts, not the timeline. Beware the inverse though — a fluent sentence that restates the post's own thesis behind a "Spot on." opener is the AI-slop signature, not insight.

KEEP short superlative fragments, including one-word ones — per Eric, 2026-10-03: "keep comments in the archive like 'astounding' (just that one word is enough, we dont need the rest for things like movie posters), same with 'worthy path toward building bigger' and 'this is amazing' kind of stuff." Set pull_quote to JUST the superlative fragment, not the surrounding sentence. TWO-WORD superlatives all count — Eric, 2026-10-23: "please include all two-word superlatives for use in future social media posters. 'excellent book!!' definitely counts." The apply-verdicts length floor was 12 characters and silently dropped "Great book!" at 11 after it had been judged a keeper; it is now 4, which rejects only empty or emoji-only records. These qualify even when the rest of the comment is a question, or when the praise is addressed to the poster rather than the book. See memory/feedback_comment_archive_fragments.md.

pull_quote MUST BE VERBATIM — it has to survive a substring check against full_text. On 2026-10-24 I silently collapsed a double space in Bob Sutton's "you are  Inexhaustible!" and had to repair the record. Copy the span, do not retype it, and assert it is a substring before writing the verdict. A one-line `assert pq in text` in the verdict-writing script makes this impossible to get wrong — it is now standard and it has held every run since. Separately, CHECK THE SPAN READS AS A COMPLETE THOUGHT: on 2026-10-26 one passed the assert while ending mid-sentence at "it's hard", because a verbatim fragment is not necessarily a usable one. A cheap guard is asserting the span ends on terminal punctuation.

A person whose POST was skipped can still have a keepable COMMENT — different lanes. Ed Magee's Oct 18 post was the textbook one-clause skip; his Oct 19 comment, "Eric's talk is still occupying mindspace, rent free", was a clean keep.

SKIP: congratulations ("Congrats!!!!"), purchase notes ("$1.99 on my kindle, purchased!"), lukewarm interest ("looks intriguing"), praise aimed at something other than the book or the talk, commenters who say they have not read it yet, questions, conversational replies, and AI-slop comments. The slop signature is a long fluent sentence restating the post's own thesis back at it — "This is exactly the board governance and mission protection conversation most directors needed to see"; several arrive per event, sometimes with HTML-escape artifacts like "Melissa#39;s". An award or milestone post draws a wave of pure congratulation — nine of them on 2026-10-26 after the Barnes & Noble announcement — and those are all skips however warm. A reading-list post draws a cluster of "got to check them out!" replies — all haven't-read-it skips.

One more skip class worth naming, because it is tempting: a sharp line the commenter is QUOTING rather than making. On 2026-10-26 a public-health professor replied with a Southern expression about reputation — the best line in the pull, and unusable, because a poster would end up attributing a folk saying to him as his own insight. On 10-27 a 478K-follower account tagged Eric with a line from The Lion in Winter, same problem at far greater reach. Judge whether the words are theirs.

The archive holds COMMENTS only — every record to date is item_kind "comment". The queue also surfaces posts; skip those. But a comment can still yield a CONTENT-side find worth acting on: on 2026-10-19 Ash Wallington posted her article URL in comments, which completed an entry shipped the day before when the link was unreachable. When you go looking for such a URL, grep the RAW archive file rather than walking the parsed structure — the queue preview truncates at 150 characters and the comment nesting is not where you expect.

CRITICAL: when a candidate's relevance depends on the PARENT post, print the parent post IN FULL before deciding. A lowercase or adjectival "incorruptible" near the top of a post is a reason to keep reading, not to dismiss — people routinely use the word casually and credit the book further down. This is how the Paige Kaye entry was nearly lost (memory/feedback_read_whole_parent_post.md).

For each YES write a verdict to /tmp/verdicts-<YYYY-MM-DD>.json with: identifier, platform, kind, source_scan, text, pull_quote, permalink, posted_at, reactions, comments_count, author, parent_post — copied from the queue entry; only pull_quote needs judgment. Then:
  python3 scripts/archive-social-comments.py --apply-verdicts /tmp/verdicts-<YYYY-MM-DD>.json
  python3 scripts/generate-comment-cards.py --all

The watermark writes itself when --apply-verdicts archives anything; there is no separate step. It had none at all until 2026-10-20, so scan_catchup.py reported this job as "never run" forever.

Note that generate-comment-cards gates on `already_have`: a commenter who is already on the timeline gets archived but produces no card. That is correct, not a bug — Bob Sutton has five entries, so his 2026-10-24 reply rendered zero cards, as did Rita McGrath's on the 25th. Do not go looking for a fault when the counts differ.

Report: posts and comments scanned per source, each verified item as one line of "who + quote", the running total across all daily files, and the below-bar candidates with reasons. "No new superlatives this cycle" is fine on a quiet day. Note if one voice is dominating the archive — Kevin Payne is 6 of 152 records as of 2026-10-27, the most of anyone, with Isabell Springer second at 5; that is flagged for Eric rather than capped, since the lane is raw material and his lines are the sharpest the X feed produces.
```

## 5. Weekly LinkedIn recall audit — `17 11 * * 0`

```
Weekly LinkedIn recall audit. Check the production scan query for drift against alternates, per memory/feedback_linkedin_query_calibration.md.

Run all three over the same 7-day window, each with waitSecs:0 then scan-triage.py (docs/SCAN-PROTOCOL.md section 1). postedLimit accepts only [any,1h,24h,week,month,3months,6months,year] — "7d" fails validation.

1. PRODUCTION: searchQueries=["Incorruptible Ries"], postedLimit="week", maxPosts=100, sortBy="date"
2. ALTERNATE:  searchQueries=["Eric Ries Incorruptible"], same params
3. BARE:       searchQueries=["Incorruptible"], same params

maxPosts MUST be 100, not 40, and pass callOptions {"maxItems": 100} on each — maxPosts alone is a soft target the actor does not honour. On 2026-09-27 both queries hit the 40 cap, so the comparison was between two truncated lists and reported false agreement — that is how a Raj Sisodia endorsement went unseen for a week. Check and report whether any query hit the cap; if one did, its result is not a valid comparison input. This is the one job where 100 is justified: the comparison is worthless on truncated lists, and this audit is the designed backstop for everything the daily scans miss.

On 2026-10-25 the BARE query hit the 100 cap (production 43, alternate 42). If it caps again, consider narrowing its window to 3 days rather than raising the cap — the bare query's job is to surface what production misses, not to enumerate every adjectival use of the word, and a truncated 7-day list is worse for that than a complete 3-day one.

The bare query is noisy (Bible verses, political theory, films, and lowercase adjectival use). Filter it for book relevance before comparing: the post body should mention Eric Ries, Lean Startup, financial gravity, or mission-lock. But note the structural reason the bare query is not redundant: a post that hashtags Eric's name (#EricRies) never contains "Ries" as a standalone token, so the two-word production query cannot match it at all. That is a mechanism, not noise. It is not the only reason, though: on 2026-10-25 all five production misses were bare-only and TWO of them did contain a standalone "Ries" token, so the two-word query also simply misses posts it should match. Do not assume closing the hashtag case would close the gap.

Compare recall, then cross-check against content/entries/ for the past 7 days. Report: each query's count, whether any hit the cap, IDs unique to each alternate (up to 10), any high-signal post that two queries returned but we never shipped, and whether the production query is missing more than 20 percent of relevant posts.

Judge by quality as well as rate. On 2026-10-04 the raw miss rate was only 7 percent, but the single missed post was a peer-tier endorsement from the co-founder of the Conscious Capitalism movement — worth escalating on its own.

Audit BOTH halves — recall and judgment. For every relevant post the production query DID return but we never shipped, check it against the inclusion memories before calling it correctly skipped. On 2026-10-11 recall was healthy (8 percent miss, no cap hits) yet the week's real finding was a judgment miss: Fora Fereydouni (Founder & CEO, Cognitai, 47 likes) sat in an Oct 6 daily list of only 13 items and was passed over, then shipped a week late by the audit. A short daily list is not a reason to skim it. The 2026-10-25 audit repeated the pattern exactly: recall was fine at 90 percent, and the real finding was two returned-but-unshipped posts, Dan Barker finishing the book and Gregory Hedges of NACD Chicago ranking Eric's talk against Ian Bremmer's. Ship anything the audit confirms was wrongly skipped.

Also audit COVERAGE, not just query shape: run `python3 scripts/scan-coverage.py --days 14` and report any day a daily source produced no archive file. These crons only fire while the REPL is idle, so a closed laptop skips a cycle silently. If a gap is real and still unbackfilled, do one catch-up pull with a derived postedLimit (scan_state.choose_posted_limit) and client-side dedup against data/archive/, then ack_gap it.

Audit DEDUP too, which is the other direction of the same failure. On 2026-10-20 a Goodreads review already on the timeline since September was shipped again because the "fresh" check compared datasets instead of comparing against content/entries/. Same-type duplicates are now a lint FAILURE, so that exact case stops at the commit; what lint still reports only as a WARNING is a mixed-type pair, sometimes legitimate (an event and a reaction to it) and sometimes not. Read those warnings and resolve each: merge, correct the mis-sourced one, or add a genuinely shared canonical page to SHARED_CANONICAL_URLS in src/lib/source-url-integrity.ts. On 2026-10-21 that exercise found a LIFT Economy episode sourced to its LinkedIn announcement, and a Thought Economics entry whose blockquote was a composite of Eric and Brian Chesky, live for three months. On 2026-10-25 all three remaining warnings were real and all three were resolved to zero: Reid Hoffman was a legitimate shared canonical page (episode plus a line from it); the Judy Samuelson pair was a true duplicate, the Aspen summit's own organiser describing her own event with a byte-identical blockquote, and the reaction was removed; and the Prosper breakfast was MIS-SOURCED, pointing at Hattie Moll's post while its archived source text was Andrew O.'s — repointing it also retired a quote attributed to Eric that existed only as an attendee's rendering. Finish the job: resolve every warning to zero rather than reporting them again next week.

Also run `python3 scripts/scan_catchup.py` alongside the coverage check — it knows each job's cadence and reports scheduled runs that never happened, which the filename-based coverage check cannot. And `python3 scripts/check-images-render.py` after a build, which reports entry images reaching no HTML. And `python3 scripts/find_ondisk_images.py`, which reports unimaged entries whose headshot is already in public/images/people/ — it found six in two days when it was still a manual grep.

If a calibration change is warranted, update memory/feedback_linkedin_query_calibration.md, docs/SCAN-PROTOCOL.md and the affected prompt in docs/CRONS.md, then commit. Otherwise make no commit beyond any entries the judgment audit shipped.
```

## 6. Evening content scan — `3 18 * * *`

```
Evening content scan. Follow docs/SCAN-PROTOCOL.md in the repo for the full standing rules (Apify call pattern, inclusion bar, TikTok blocking rule, entry/image/verify/ship steps, reporting format). Read it first — section 1 now carries hard billing caps and the derived-window rule.

Derive the window, do not hardcode it (scan_state): postedLimit = choose_posted_limit(read_watermark(src), now). record_run() each dataset id at launch; clear_run() + write_watermark() after the archive is written. A widened window always needs dedup against data/archive/.

Sources this cycle — run each with waitSecs:0, then scan-triage.py per the protocol:
1. TikTok profile (clockworks/tiktok-profile-scraper, profiles=["ericriesactual"], resultsPerPage=10) — ONLY on Mon/Wed/Fri. On other days skip it entirely and say so in one line. Compute the weekday, never assume it. When you do run it, the blocking rule applies to every video without exception: grep the id against data/ai-tiktok-denylist.json AND confirm Eric is on camera. The reliable on-camera check is to download videoMeta.coverUrl and LOOK at it — caption text is not evidence, and a watermark in the corner names the podcast a clip was cut from (that is how the 2026-10-22 clip at 72 likes, the week's biggest, was identified as a Startup Leap promo cut). If you cannot confirm on-camera, skip. Genuine on-camera clips still get skipped when they are promo cuts of an episode already on the timeline, and Eric's own event announcements never qualify. Photo slideshows never qualify.
   WHAT MAKES A CLIP SHIP IS THE ARGUMENT IT STARTS, NOT THE PLAY COUNT. 2026-10-21's "ask whether the company is mission-driven, then ask how they know" shipped at 379 plays because three separate people took it up on X. 2026-10-26's "We've accidentally designed companies to behave like sociopaths" shipped at 307 plays and NINE X replies, several arguing with the premise rather than agreeing. Check the X mentions dataset for replies to the clip before deciding — and search for the ARGUMENT, not the catchphrase: not one of those nine replies contained the word "sociopaths", so grepping the slogan would have found nothing.
2. LinkedIn @-mentions (harvestapi/linkedin-post-search, mentioningMember=["https://www.linkedin.com/in/eries/"], maxPosts=40, sortBy="date", callOptions {"maxItems": 25}).
3. Twitter/X @-mentions (apidojo/tweet-scraper, searchTerms=["@ericries"], maxItems=20).

AFTER triaging the X mentions, feed that same dataset to the comment archive — it costs NOTHING extra, the items are already paid for:
  python3 scripts/archive-social-comments.py data/archive/twitter-raw/<YYYY-MM-DD>-mentions.json --platform twitter --scan-source=twitter-mentions
Then classify the queue the same way the Mon/Wed/Fri LinkedIn job does, write verdicts, apply, and run generate-comment-cards.py --all. pull_quote must be VERBATIM — copy the span rather than retyping it, and assert it is a substring of full_text before writing the verdict; on 2026-10-24 I collapsed a double space in Bob Sutton's "you are  Inexhaustible!" and had to repair the record. Also check the span reads as a COMPLETE THOUGHT: on 2026-10-26 one passed the assert while ending mid-sentence at "it's hard". generate-comment-cards gates on `already_have`, so a commenter already on the timeline archives but produces no card — correct behaviour, not a fault to chase (Sutton on the 24th, Rita McGrath on the 25th, both zero cards).

Per Eric 2026-10-20 ("you can add the twitter and cardono comments to the comment archive. expand it to include cases like that") this lane is NOT limited to superlatives. Two-word superlatives all count — "Great book!", "excellent book!!" — and a sharp observation that uses the book's argument qualifies even with zero likes and no praise — Kevin Payne's reply "Metrics outlive principles. Once the dashboard rewards extraction, the people who remember why the company worked stop getting promoted" is the model. A reply to Eric inherits the book anchor; it does not have to name the book. Still skip questions ("is the talk gonna pull from incorruptible"), conversational replies, promo-agency filler, tweets that merely quote the book back, and sharp lines the commenter is QUOTING rather than making — on 2026-10-26 a professor's Southern expression about reputation was the best line in the pull and unusable, because a poster would attribute a folk saying to him as his own.

When an event Eric spoke at has just happened, check whether the organiser has published a post-event quote. The NACD entry carried only its pre-event agenda blurb until NACD's own account published what he actually said; swapping that in, moving the summary to past tense and dropping the "upcoming" tag is a real upgrade worth doing the morning after any major event. That check earned itself on 2026-10-22: post-event posts revealed Eric was in conversation with Krista Tippett at Masters of Scale, which no pre-event material named, and the event entry gained the fact along with its move to past tense. Madeline McIntosh calling that conversation her personal highlight — from a programme with Reid Hoffman, Eric Schmidt and Maria Ressa on it — was the entry; a ranking from someone with that much to compare against is not a name-check. Gregory Hedges, President & CEO of NACD's Chicago chapter, is the same shape: he picked Eric as one of the Summit's three most provocative talks alongside Ian Bremmer and Elliott Management's Jesse Cohn.
BUT DO NOT FAKE IT. On the evening of 2026-10-27, hours after the Berkeley Newton lecture, every piece of SCET material still read "Don't miss... live next Tuesday" — so the upgrade was correctly NOT done. When that happens, say so explicitly and hand the retry to the morning prompt WITH the deadline, because an event rotating off the rail still reading as upcoming is the failure mode and nobody looks at it afterwards.

ATTENDEE NOTES ARE NOT ORGANISER QUOTES. An attendee writing "Eric Ries: <sentence>" is recording their own paraphrase, and that sentence must never become the parent entry's blockquote attributed to Eric. Ship it as a reaction whose blockquote_source is the attendee, with a title that says whose notes they are — Caroline Dell's Masters of Scale write-up on 2026-10-23 is the pattern. The same post can still enrich the parent through source_urls. This is the Chesky-composite failure class approached from a new direction, and the 2026-10-25 recall audit found a live instance: the Prosper breakfast event carried "Corruption breaks the logic of capitalism itself." as Eric's words via an attendee, while its archived source text was a THIRD person's post entirely. Check that an event's source_url matches the source text actually stored for it.

Reactions have NO numeric ceiling (Eric, 2026-10-14: "relax the five reactions ceiling from now on, if quality is high"). Quality is the only gate — if the single argument against shipping a reaction is that the parent already has N, ship it. Still skip the "great event!" class, which has two recurring shapes: a name-list where Eric is one of several speakers, and a post that gives him one clause before moving to a different session for its real takeaway (David Buck 2026-10-17, Ed Magee 2026-10-18 and Eva Zauke 2026-10-20 — one sentence among four speakers — are the textbook cases). Leslie Feinzaig's Masters of Scale post on 2026-10-22, which tags Eric among a dozen friends, is the purest form of it; Susie Jaramillo's on 10-26 and Abby Falik's on 10-27 are the same shape at 19 and 5 reactions. Brendan Fay's on 2026-10-23 is the near-miss worth studying: Eric's bullet carried a real argument, but it was one of five and the post's own stated favourite line was about AI, so it enriched the parent instead of shipping. Chun Schiros's NACD recap is the same shape and was skipped FOUR cycles running — it also closes "cant wait to dive deep in this new book!", which is a haven't-read-it on top of a name-list.

But do NOT confuse that with a field observation. A credible practitioner reporting that the ideas are SPREADING — "more and more builders choosing public benefit missions" (Peter Ward, ex-Oura, 2026-10-17, which Eric reversed my skip on) — ships even as one paragraph inside an otherwise off-topic post with low engagement. Adoption evidence from someone with standing to see it is a category the timeline is short of, and the host post's topic is a weak signal against it. The test is whether the paragraph asserts something about the world or merely nods at the book. See memory/feedback_field_observations_ship.md. The strongest form of it to date: the Toronto book group Natasha Freidus asked for in September actually met on 2026-10-22 and left organising, which is the ideas becoming an activity rather than a reaction. Natalie Reitman-White on 2026-10-23 is the same shape at 5 reactions. Isabell Springer on 10-26 is another: one line reporting that she and Peter Ward are BOTH incorporating as public benefit companies because of the book — Ward being the same practitioner from the October field observation, now acting on it.

INSTITUTIONAL ADOPTION is the strongest form of all and it is worth chasing to the source: on 2026-10-24 a CEO mentioned in passing that a summit's theme was based on the book, and the organiser's own page turned out to name Incorruptible and financial gravity directly — a 200+ invite-only convening framing itself on the argument, with Eric not even speaking. Verify on the organiser's page, not the post that mentions it, and type it media rather than event so nothing implies Eric appears. A related and equally strong shape is PLACEMENT: George Chmael II, CEO of Council Fire, on 2026-10-26 set Eric's shareholder-primacy piece alongside Paul Polman and the World Inequality Lab as "the fourth independent voice in the last six months to arrive at the same structural diagnosis", credited him specifically with the organizational mechanics, and is building a regional strategy on it. Someone placing the argument in a field is making a claim about the world.

A NEWS EVENT CAN PULL SEVERAL PEOPLE TO THE BOOK AT ONCE — judge each post, not the pattern. Anthropic's S-1 filing on 2026-10-27 drew several; most were one line among hashtags and were skipped, and one, David Nelson of FoundersForge, used the book to explain the whole structure and named a concrete test, so it shipped. Beware counting a cluster before checking it: on 10-26 I reported "three people independently" and two of the three turned out to be one 27-follower account posting the same sentence twice sixty seconds apart. Count accounts, not posts, and look at follower counts before using the word independently.

A promotional company post is often better used to ENRICH the parent entry than shipped as its own: SEEK Alabama's booth post documented that Innovate Alabama sponsored the Inc. 5000 book signing, which belonged in source_urls on the event, not on the timeline. Same for an artifact travelling — Trent Wakenight's graphic recording of the Responsive talk was republished a month later in a sketchnote roundup, which belongs on the artifact's own entry. And same when a company account publishes something its founder already posted: Wunderdogs' 10-26 interview post looked like a clean new entry but covered the conversation Daria Gonzalez had posted herself on the 23rd — a different post about the same thing, which the source_url grep cannot catch and only reading does.

DEPTH CAN CARRY AN ENTRY WITHOUT PRAISE (Eric, 2026-10-19). A substantive argument that uses the book — even at 2-3 reactions — ships. The Christopher Marquis NYT op-ed on shutting down business schools has now pulled three separate people into citing Incorruptible as the answer. Michael Kobori naming it as the influence on his own governance series is the same shape, as is Mo Salah reading Red Bull's engine programme through it at zero reactions, and Logan Yonavjak's "structure constrains bad leaders without necessarily producing good ones" — a disagreement that engages rather than dismisses. Dan Barker's 2026-10-22 post is the pattern for a reader finishing: his first two entries were mid-read reactions, and the third took the argument somewhere new, against the economics of AI. Nick Hague on 10-26 is the pattern for a reader supplying evidence: he states financial gravity correctly and then gives his own case, "When I sold my agency, the culture began to shift... Decisions that would have taken five minutes now took five months." Sebastian Ross on 10-27 is the pattern for a SECOND entry from the same person being justified: his June entry was a recommendation, this one brings a 250,000-founder study showing 88% end with zero exit value and lands on "Governance rules and term sheets are the point of attack." The inverse also holds, and it recurs: Martin Aguinis's full-circle story was the highest-engagement post of 2026-10-22 at 54 reactions and was skipped because it is entirely about The Lean Startup, Alejandro Pinzon's (27 reactions, top post of 10-23) for the same reason; and Ronei Vinagre's on 10-26 at 293 reactions — the biggest of the week by far — because it is a Portuguese reading list naming A Startup Enxuta. Engagement does not convert a Lean Startup story into an Incorruptible one.

PRAISE AIMED AT ERIC COUNTS, NOT ONLY PRAISE AIMED AT THE BOOK (Eric, 2026-10-28: "it's ok to start expanding our praise criteria to include people who are praising eric directly (so long as it's incorruptible-related) even if they only mention the book as one component of that praise"). Baratunde Thurston's Masters of Scale write-up on 10-28 is the model: the book is named once, in passing, and the rest is about Eric owning his role in what The Lean Startup helped create — it ships, and the blockquote is the WHOLE paragraph about him, not a tidy two-sentence cut of it. This does not reopen the bare @-tag, the name-list recap, or a Lean Startup story with no Incorruptible content; the connection still has to be there, it just no longer has to be the whole post. See docs/SCAN-PROTOCOL.md section 3.

A warm reply from someone already heavily represented is archive material, not a sixth entry. Bob Sutton on 2026-10-24 — "I am starting to think you are  Inexhaustible!" — is a lovely line from a Stanford professor with 73K followers, and it was still a skip: encouragement rather than a new argument, from a man with five entries already. Ask what the post ASSERTS, not how notable the poster is.

Verify any named concept before attributing it to the book. Readers coin their own: "mission gravity" was Kevin Sam's inversion, not Eric's term, while "harder is easier", "financial gravity", "extraction primacy" and "emperor for life" are his in his own words — the last two confirmed by grep on 10-26 and 10-27. Grep data/archive/source-texts/ and data/archive/transcripts/ before writing one into a summary. The same grep settles whether a case study being retold is actually the book's — Ollie Forsyth's capped-markup retailer checked out as Sol Price at FedMart on 14% margins, "whose story is in the book" in Eric's own words — and whether a phrase is Eric's or the poster's: "values in your structure outlive you" appears nowhere in the sources, so it was framed as Forsyth's reading rather than Eric's point.

NEVER ASSEMBLE A BLOCKQUOTE FROM NON-ADJACENT SENTENCES. On 2026-10-25 a better Cranlana quote was proposed as three sentences that turned out to have a fourth between them; fetching the page and asking for the exact contiguous passage caught it. If you want more than one sentence, verify contiguity at the source before writing it. And prefer a span free of hashtags or Unicode-bold characters — Sebastian Ross's sentence naming the book used bold Unicode, so the entry took the clean sentence before it.

Do not invent a credential to make an attribution_title read better. On 2026-10-23 I wrote "formerly Antler" into an entry from nothing but a vague memory and had to cut it before commit; the X headline said only "Building NEW MEDIA channels". Use what the source states, or state less (memory/feedback_attribution_titles.md).

BEFORE writing any entry, grep content/entries/ for BOTH the source_url and the author. Same-type duplicates are now a lint failure so the worst case stops at the commit, but new-to-the-dataset is not new-to-the-timeline and the check should not be doing the thinking. Check public/images/people/ for an existing file before downloading a face too — on 2026-10-25 a duplicate dan-barker-klasma.jpg was created and deleted when dan-barker.jpg was already there.

Also: pick 2-3 unimaged older entries from the backlog and source photos. Query with BOTH image and attribution_image null. RUN `python3 scripts/find_ondisk_images.py` FIRST — it reports unimaged entries whose headshot is already in public/images/people/, `--wire` attaches the unambiguous ones, and rejected matches go in data/ondisk-image-skips.json with a reason so they stop reporting. It found six in two days before it was a script. The LinkedIn avatar archive gives zero matches for the old entries and YouTube thumbnails are exhausted, but the web is NOT dry for named executives — speaker bureaus (speakabout.ai og:image, 1000x1000) and company newsrooms carry clean headshots, which is how Tatyana Mamut and Carolyn Groobey were sourced, and Madeline McIntosh from a Lee Enterprises board-director profile. Wikimedia Commons is worth a try for anyone with a Wikipedia page — Garry Tan on 2026-10-23, and Roy Bahat on 2026-10-24 from a file literally named "Roy Bahat, head of Bloomberg Beta", matching the entry's own attribution_title. A company team page can work where its og:image does not: Chike Aguh came from kaporcenter.org on 2026-10-25, but only the uncropped original was usable — the 640x360 derivative the page linked cut his eyes off. Confirm a profile page is the same person before using its photo. Order to try: find_ondisk_images.py, speaker bureau, Wikimedia, company newsroom or about page, fellowship/award bio, personal site. Square-crop with `sips -c <h> <h>` then resize to 600, then LOOK at the result before wiring it. Stop when the name is ambiguous across several people — no image beats a wrong face, and "no new image found" is a fine answer; David Bland and John Paul Farmer both came up dry on 2026-10-23, Farmer again on 10-24, and SkyDeck and Vistage on the 25th, Sri Rajan, Marsha Acker and Sasha Orloff on the 26th, and Ann Armbrecht and the Fourth Effect on the 27th. Org and event logos go in /images/events/ — there is no /images/orgs/. Reject og:images that are grids of other people's faces or generic sitewide share cards: Goodword's, Interintellect's salon banner, the American Botanical Council logo standing in for Ann Armbrecht, and the Fourth Effect's social-preview.jpg were all that shape. AFTER attaching any image run `npm run build && python3 scripts/check-images-render.py`, which reports entry image paths reaching no HTML.

Finish with backfill-quote-cards, backfill-source-texts, verify-quotes, lint, commit, push.
```

## 7. Sidebar curation — `27 19 * * *`

```
Sidebar curation. Re-evaluate the past 30 days of content/entries/ and decide the top 8 entries carrying type_metadata.featured (the "What's New" rail).

Criteria per memory/feedback_sidebar_flags.md and memory/feedback_highlights_row_grows.md:

WHAT'S NEW (featured, exactly 8) — third-party momentum only: events, endorsements, real news. Prefer upcoming book-tour events, heavyweight endorsements, podcast appearances, viral coverage. Rotate an event out the day after it happens. Eric's own posts are auto-excluded by the index filter (isSelfAmplification keys off both the speaker and the venue), so do not bother flagging them — an entry sourced to Eric's own LinkedIn or TikTok will never render here no matter what flag it carries.

Only standalone types have ever been featured — endorsement, event, podcast, media, milestone. A type=reaction is a child of its parent and is not a candidate, however high its engagement: Christopher O.H. Williams at 57 reactions on 2026-10-19 was the highest-engagement post of the NACD wave and still was not eligible. Nor is type=review, which has never been featured. In a busy cycle that can mean most of the day's output is ineligible — on 2026-10-26 five of six ships were reviews or Eric's own TikTok. But CHECK rather than assume: on 10-27 two of four ships were reviews and it would have been easy to write the day off, when the Itamar Gilad interview was type=media and belonged in the queue.

Be conservative. Churn the featured set only for a clearly better candidate; a single swap is a normal night's work and no change at all is a fine outcome. When an event is rotating out tomorrow anyway, do not also churn a second slot tonight — one change at a time. A swap made earlier the same day at Eric's request counts as that cycle's one change.

Tiebreakers that have actually decided calls:
- Composition. On 2026-10-16 the rail held three events, two media, two endorsements and zero podcasts, which is what sent a 15-day-old milestone out for a 38K-subscriber interview.
- Scarcity can outrank composition. On 2026-10-20 Berkeley Newton went in as a FOURTH event, against the usual balance rule, because the tour is ending and forward-looking slots are now the scarce thing. Design Observer came out as the older of two media slots.
- Reach, as a reason NOT to swap: a 1,570-subscriber podcast does not displace a 38,400-subscriber one just for being newer. Note the limit of that test — it is a reason not to DISPLACE a sitting entry, never a bar to filling a slot that has actually emptied.
- Quote strength over freshness. On 2026-10-18 Kim Scott — allowlisted heavyweight, same day — did not displace Alistair Croll, because "such an important book!" appended to a reshare is thinner than Croll giving away a dozen copies and calling it "an incredibly important reset for startups and capitalism itself".
- An ARM'S-LENGTH endorsement outranks a warmer one from closer in. Carol Van Den Hende was declined on 2026-10-26 partly on quote strength and partly because she had disclosed meeting Eric while preparing his talk at her own company. That does not disqualify an entry; it weighs against it for a momentum rail.
- A QUEUED pick is not a commitment. On 2026-10-24 the slot freed by B Academics went to Courtois rather than to Giant Robots, which had been queued for it on the 22nd — before Courtois existed. When composition is neutral between two candidates, weight decides, and a candidate that arrived after the queue decision deserves to be weighed. Re-derive the comparison; do not just execute the note.
- But do not let a queued pick slide forever either. Three consecutive pass-overs starts to read as a verdict when it was only ever timing. If the same entry is displaced a fourth time, say so explicitly in the report and justify it on its merits, not on the arrival of yet another newer item.

CURRENT STATE (2026-10-27 evening, re-verified in the DOM: bounded grep returned exactly 8, sorted(rail) == sorted(featured) asserted, quote-cards 33 == highlight-flagged 33): 2 events, 3 media, 2 endorsements, 1 podcast — SOSV (11-04), Berkeley Newton (10-27), Jean-Philippe Courtois (10-24), Barnes & Noble's Best Books of 2026 — Business (10-23), Rita McGrath's Fast Company piece, Stanford eCorner, NEW ECONOMIES podcast, and Croll. UNCHANGED on the 27th: Berkeley Newton RAN today, so it rotates out tomorrow rather than tonight, and no slot was free. Note the evening scan deliberately did NOT do the post-event upgrade on it — every piece of SCET material still reads "Don't miss... live next Tuesday", so there is no organiser quote to swap in yet. The morning scan should retry that before this job runs again.

QUEUED FOR THE NEXT FREE SLOT — FOUR candidates for ONE slot, ranked. Berkeley Newton frees a slot on the 28th, taking the rail to 1 event / 3 media / 2 endorsements / 1 podcast.
  (a) Giant Robots #628 (thoughtbot, 2026-10-22, 34,200 subscribers) — passed over three times, every time by a stronger entry taking the slot it was waiting on, never by a judgement against it. Would make podcasts 2. A FOURTH pass-over has to be argued on its merits per the tiebreaker, not on a newer arrival.
  (b) The Fourth Effect summit (media, 10-24, 200+ invited leaders, programme built on the book, Eric not speaking) — the strongest institutional-adoption item on the timeline. Would make media 4.
  (c) Itamar Gilad's interview (media, 10-27) — a genuinely new Q&A on AI and founder mode, from the creator of the GIST framework. Ranks below (b) because both make media 4 and the Fourth Effect is the heavier claim, and below (a) on composition and reach.
  (d) Carol Van Den Hende (endorsement, 10-26, Mars Inc) — good quote, 2 reactions, and the closeness disclosure.
Composition still favours (a): media is the over-weighted column at three and the rail has one podcast. Pre-derived, not a commitment — but if (a) is passed over a fourth time, say why on its merits.

Keep these two paragraphs current — they are how the next run knows what it is looking at, and what the last run decided, without re-deriving either.

EVENT PIPELINE — answered, do not flag nightly. A targeted search on 2026-10-20 found no unscheduled dates; the tour is concluding by design and SOSV on Nov 4 is the last event. Raise it once when that slot empties, then stop. The rail will keep working as a momentum surface — the scan produced eleven standalone entries in the six days to Oct 19 — it just stops answering "where to see Eric next". See memory/project_event_pipeline_winding_down.md.

HIGHLIGHTS (highlight) — GROWS, NEVER TRIMMED. Lint enforces a floor. Only ADD; never remove a highlight flag from any entry, including ones dropping out of What's New. The name must already be on HIGHLIGHT_ELIGIBLE_ENDORSERS in scripts/lint-entries.ts. Adding a new name is Eric's editorial call — ship such an entry with type_metadata.sidebar_quote instead and ask via AskUserQuestion, never in prose. The operative distinction is author tier versus CEO tier: a named author with a body of work (Steve Blank, Nir Eyal, Rory Sutherland, Raj Sisodia) is worth asking about; the CEO of a notable company is not, however on-thesis the endorsement (memory/feedback_highlights_row.md). Academic-publication credentials (a Springer monograph, a lectureship) are not the same as that body-of-work recognition, and neither is one leadership title alongside a board career — Michael Kobori, former Chief Sustainability Officer at Starbucks and a board director, was correctly NOT asked about on 2026-10-20, and neither were Madeline McIntosh (publishing chief executive), Caroline Dell and Natalie Reitman-White (CEO and practitioner tier), or Jean-Philippe Courtois (former Microsoft president, business-school chairman, podcast host) on the 24th — the heaviest endorsement of the month and still not author tier by the stated test.

"Only ADD" does not mean add every eligible instance. Kim Scott is allowlisted and already carries three faces in the row; her 2026-10-18 one-liner was deliberately left unflagged because a fourth identical face with a weaker quote makes the row repetitive, not stronger. Declining to add is not trimming — the floor stays put. The quote has to earn the face even from an eligible name: Rita McGrath is author tier by the stated test, but "gave a thought provoking keynote on financial gravity" is descriptive rather than unequivocal praise, so she was not asked about on 2026-10-21.

Note: lint forbids sidebar_quote and highlight on type=reaction entries — those flags belong on the parent.

Format a highlight as "Name: 'verbatim short quote'".

Use Edit to MERGE flags into the existing type_metadata object, never overwrite it.

Then verify, in this order:
  npx tsx scripts/lint-entries.ts
  npm run build
  grep the rendered dist/index.html to confirm the change actually reached the DOM
Do not trust the JSON alone — twice, edits landed in a component that produces no output (memory/feedback_verify_in_dom.md). Confirm the new entry appears in the What's New block, and count `class="quote-card"` occurrences in dist/index.html against the number of entries flagged highlight; they should match (33 as of 2026-10-27, verified) and must not drop. Check the floor on any night an entry was REMOVED as well as added — the 2026-10-25 recall audit deleted a duplicate reaction, and that is exactly when a silent drop would happen. BOUND the What's New grep — stop it at the "Highlights" heading rather than taking a fixed character window. An unbounded 6000-char window on 2026-10-23 ran into the Highlights row and appeared to show 11 rail entries; bounding it on the 24th returned exactly 8 matching the flagged set. Assert `sorted(rail) == sorted(featured)` rather than eyeballing the count.

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
