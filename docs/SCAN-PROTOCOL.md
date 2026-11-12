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

**The comment archive takes X as well as LinkedIn** (2026-10-20). The producing
script is `scripts/archive-social-comments.py`, with `--platform linkedin|twitter`;
every record carries a `platform` field. The evening scan's existing
`@ericries` mention pull feeds the Twitter lane at **no extra Apify cost** — the
dataset is already paid for by the mention scan. A reply to Eric inherits the
book anchor exactly as a comment on his LinkedIn feed does, so the reply itself
does not have to name the book, and praise is not required: a sharp observation
that uses the argument counts.

**Every job writes its watermark when it finishes** — including the comment
archive, whose key is `linkedin-comments`, and which had no watermark at all until
2026-10-20. The watermark is the only record that a job ran; without one
`scan_catchup.py` reports the job as never having run and the next scan widens its
window for no reason. Write it after the archive is on disk, never before.

**Catch-up is cadence-aware; absence of a file is not.** `scan_catchup.py` holds
each job's cron expression and asks which scheduled fire times went by without the
job running. Use it rather than reasoning from dated filenames — two of the seven
jobs are not daily, and on 2026-10-20 a Monday-only scan was reported missed on a
Tuesday and re-run at real cost. It is free and instant; run it at session start
and in the watchdog.

When a gap has been backfilled, call `ack_gap(source, date, note=...)` so
`scan-coverage.py` stops reporting it. Catch-up pulls deliberately do not count
as coverage — otherwise a backfill would mask a real hole — which means an
un-acked fixed gap reports forever. The history stays in
`data/archive/.gap-acks.json`; only the signal clears.

**Always pass `callOptions: {maxItems: N}`.** These actors bill per dataset
item, and `maxPosts` is a soft target the actor does not honour: on 2026-10-14
the comment-archive runs were given `maxPosts: 30` and `maxPosts: 40` and
returned **130 posts each**. `maxItems` is the only hard billing cap. Measured
over Oct 10-14, the two comment-archive runs alone were 763 of ~1,524 items
pulled — **50% of all Apify volume for a job that ships nothing to the site**.

Standing caps (raise only with a reason, and say so in the report):

| job | call | maxItems |
|---|---|---|
| comment archive | author feed | 250 |
| comment archive | keyword | 250 |
| morning scan | LinkedIn ×2 | 25 each |
| evening scan | LinkedIn @-mentions | 25 |
| weekly audit | each of 3 | 100 (needed for a valid comparison) |

The comment-archive caps were 40 until 2026-10-28, when a total-item cap was found to be starving the author feed of POSTS — the stream interleaves posts with their comments, so comments crowded posts out and two days were never scanned. Cap each dimension at its own knob and keep `maxItems` clear of normal volume (`docs/postmortems/2026-10-28-item-cap-starved-the-post-feed.md`). Also set `maxTotalChargeUsd` explicitly: Apify applies an invisible $0.50 default.

Apify is on a **$29/month** limit and hit 50% by Oct 14. When a scan's triage
shows the cap was reached and the tail still looked relevant, say so in the
report rather than silently raising it.

```
1. mcp__apify__call-actor  { actor, input, waitSecs: 0 }   -> runId + datasetId
2. python3 scripts/scan-triage.py <datasetId> \
       --platform linkedin|twitter|tiktok|youtube \
       --archive data/archive/<src>-raw/<YYYY-MM-DD>-<scan>.json
```

Step 2 polls until the read matches the dataset's `itemCount`, archives the raw
items (this is what satisfies the full-source-text requirement in §5), and prints
a compact triage table. **Never use `get-dataset-items` or `get-actor-run`** —
`scan-triage.py` replaces both.

**And never hand-roll the fetch either.** On 2026-11-02 two jobs in one session
wrote their own poll loop that stopped at the FIRST non-empty response. The
Goodreads scan archived 30 items and reported on them; the dataset held 50, and
the run was still writing. Twenty reviews went unassessed — the same twenty-review
loss the removed `maxItems` cap used to cause, reproduced by hand on the day the
cap was correctly left off. The comment-archive pull was worse: 2 items and 1
item against eventual counts of 98 and 60.

A non-empty dataset is not a finished dataset. `scan-triage.py`'s `fetch()` is
the only sanctioned reader because `itemCount` is the authority and it waits for
the read to match; a run in RUNNING state is still writing. If a job genuinely
cannot use the script, read the run's status to a terminal value FIRST and then
compare `len(items)` against `itemCount` — and say both numbers in the report.

Useful flags: `--since YYYY-MM-DD`, `--new-only`, `--width N`.

**If an Apify call hangs silently (no error, several minutes):** that is *not*
the stale-session signature (which errors explicitly with "Session ID not
found"). Retry once with `waitSecs: 0`; if that returns promptly the transport is
healthy and only the long-poll is wedged — carry on. A genuine stale session
needs the user to `/mcp` reconnect; tell them and wait rather than degrading to
WebSearch.

### Claims about how the runtime behaves need a probe, not an inference

When a scheduled job does not run, the temptation is to explain it from the one
case in front of you and ship a fix. That produced two wrong diagnoses in two days
(2026-10-19 and 2026-10-20, see `docs/postmortems/`): ordering, then turn
duration, neither tested, each shipped as a fix that then consumed the evidence
for the next day's investigation.

A behavioural claim about the scheduler — "recreating a job skips its next match",
"a cron cannot fire mid-turn" — is cheap to test directly: `CronCreate` a
disposable job a few minutes out whose whole prompt is to report the time and
delete itself.

**Give a negative result hours, not minutes.** The documented 15-minute jitter
cap is not the real bound: two probes on 2026-10-20 fired **50 and 30 minutes**
past their match, the second with a completely idle REPL. Declaring the first one
"did not fire" after nine minutes produced a third wrong diagnosis on top of the
two above. "Has not fired yet" is not "did not fire". Those probes did establish
two things worth keeping: lead time at creation is irrelevant (5 minutes and 89
both ran), and due jobs **queue** rather than expire, so a busy REPL delays work
without destroying it.

Note that `CronList` does **not** expose next-fire time, so there is no way to
verify a roll took effect except by waiting for it.

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
- **Praise aimed at ERIC counts, not only praise aimed at the book** (Eric, 2026-10-28:
  "it's ok to start expanding our praise criteria to include people who are praising eric
  directly (so long as it's incorruptible-related) even if they only mention the book as one
  component of that praise"). The test is whether the praise is Incorruptible-related, not
  whether the book is its subject. Baratunde Thurston's Masters of Scale write-up is the
  model: he names the book once, in passing, and the rest is about Eric owning his role in
  what the first book helped create. That ships. This does NOT reopen the bare @-tag, the
  name-list recap, or a Lean Startup story with no Incorruptible content — the connection to
  this book still has to be there, it just no longer has to be the whole post.
- **Quote the whole passage about Eric, not a tidy fragment of it** (same note). Where someone
  writes a sustained paragraph, the blockquote is that paragraph, provided it is contiguous.
  I had trimmed Thurston's to two sentences and Eric asked for all of it.
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
  The boundary case, settled by Eric 2026-10-27: M S Sriram (professor, IIM Bangalore) reviewed the book in
  Business Standard, applied the governance-fortress framework to the Tata Sons crisis at length, called the
  chapters on Ikea, Patagonia and Mondragon "the most valuable", and closed approvingly — but wrote that "the
  problem with the book is the way it opens with contradictory outlandish claims". Eric: "nah let's skip it".
  The distinction against Joshua Pritikin, shipped the day before on a disagreement: Pritikin called the
  diagnosis good and built UPWARD from it; Sriram disputes the central empirical claim. Extending ships,
  disputing the premise does not — however serious the outlet. Do not re-evaluate this piece; it is archived
  at `data/archive/web-raw/2026-10-27-business-standard.json` and the answer is no.

### What ships and what does not — the case law

Moved here from the evening-scan prompt on 2026-11-08, verbatim. It had grown to
24.4k by accumulating one worked example per cycle and retiring none, and a prompt
re-emitted in full on every roll is the wrong place for rules that have not changed
in weeks. The examples are the point — each one is a call that was actually made —
so they are kept whole rather than summarised.

Reactions have NO numeric ceiling (Eric, 2026-10-14: "relax the five reactions ceiling from now on, if quality is high"). Quality is the only gate — if the single argument against shipping a reaction is that the parent already has N, ship it. Still skip the "great event!" class, which has two recurring shapes: a name-list where Eric is one of several speakers, and a post that gives him one clause before moving to a different session for its real takeaway (David Buck 2026-10-17, Ed Magee 2026-10-18 and Eva Zauke 2026-10-20 — one sentence among four speakers — are the textbook cases). Leslie Feinzaig's Masters of Scale post on 2026-10-22, which tags Eric among a dozen friends, is the purest form of it; Susie Jaramillo's on 10-26 and Abby Falik's on 10-27 are the same shape at 19 and 5 reactions, and Nazanin Ash's on 10-28 — a CEO's eight-session recap giving Eric one line — is the same again. Brendan Fay's on 2026-10-23 is the near-miss worth studying: Eric's bullet carried a real argument, but it was one of five and the post's own stated favourite line was about AI, so it enriched the parent instead of shipping. Chun Schiros's NACD recap is the same shape and was skipped FOUR cycles running — it also closes "cant wait to dive deep in this new book!", which is a haven't-read-it on top of a name-list. Marcela Manjarrez's NACD recap on 10-28 is the same pattern again, and was skipped the same way — but it carried a real artifact, the four-dimension governance model (compliance, purpose, coherence, integrity), which was verified as Eric's own phrasing in the Leading Learning transcript and added to the NACD event's source_urls. A name-list recap can still be worth mining even when it is not worth shipping; Dougal Shaw's 10-30 magazine-issue promo was the same, naming three profile interviews and enriching the existing Shaw entry with the fact that his went to print.

But do NOT confuse that with a field observation. A credible practitioner reporting that the ideas are SPREADING — "more and more builders choosing public benefit missions" (Peter Ward, ex-Oura, 2026-10-17, which Eric reversed my skip on) — ships even as one paragraph inside an otherwise off-topic post with low engagement. Adoption evidence from someone with standing to see it is a category the timeline is short of, and the host post's topic is a weak signal against it. The test is whether the paragraph asserts something about the world or merely nods at the book. See memory/feedback_field_observations_ship.md. The strongest form of it to date: the Toronto book group Natasha Freidus asked for in September actually met on 2026-10-22 and left organising, which is the ideas becoming an activity rather than a reaction. Natalie Reitman-White on 2026-10-23 is the same shape at 5 reactions. Isabell Springer on 10-26 is another: one line reporting that she and Peter Ward are BOTH incorporating as public benefit companies because of the book — Ward being the same practitioner from the October field observation, now acting on it. Stephanie Pierucci on 10-28 is the publishing-trade version: a 2x WSJ bestselling writer and publishing CEO naming it one of two books she personally hand-sold this year, "recommended to 3 dozen people", inside a long post about why most books never sell.

INSTITUTIONAL ADOPTION is the strongest form of all and it is worth chasing to the source: on 2026-10-24 a CEO mentioned in passing that a summit's theme was based on the book, and the organiser's own page turned out to name Incorruptible and financial gravity directly — a 200+ invite-only convening framing itself on the argument, with Eric not even speaking. Verify on the organiser's page, not the post that mentions it, and type it media rather than event so nothing implies Eric appears. The 10-29 David Banks post is the in-house version and the strongest of its kind: the CEO of AdventHealth, one of the largest non-profit health systems in the US, reporting that he has been working through the book with his leadership team and turning it into three standing questions — corroborated the next day from inside the same institution by Michael Paradise of its Leadership Institute, on a second reading. A related and equally strong shape is PLACEMENT: George Chmael II, CEO of Council Fire, on 2026-10-26 set Eric's shareholder-primacy piece alongside Paul Polman and the World Inequality Lab as "the fourth independent voice in the last six months to arrive at the same structural diagnosis", credited him specifically with the organizational mechanics, and is building a regional strategy on it. Someone placing the argument in a field is making a claim about the world. Note the limit: when the same person restates the same placement in a later post, that is not a second entry — Chmael's 10-28 post repeated the Polman/World Inequality Lab framing inside a piece about voting, and was skipped.

A NEWS EVENT CAN PULL SEVERAL PEOPLE TO THE BOOK AT ONCE — judge each post, not the pattern. Anthropic's S-1 filing on 2026-10-27 drew several; most were one line among hashtags and were skipped, and one, David Nelson of FoundersForge, used the book to explain the whole structure and named a concrete test, so it shipped. The filing kept pulling people in for days: Faolan Sugarman-Lash on 10-28, ten years in social impact, read the S-1 as the argument becoming practice and shipped at 5 reactions. Beware counting a cluster before checking it: on 10-26 I reported "three people independently" and two of the three turned out to be one 27-follower account posting the same sentence twice sixty seconds apart. Count accounts, not posts, and look at follower counts before using the word independently.

A promotional company post is often better used to ENRICH the parent entry than shipped as its own: SEEK Alabama's booth post documented that Innovate Alabama sponsored the Inc. 5000 book signing, which belonged in source_urls on the event, not on the timeline. Same for an artifact travelling — Trent Wakenight's graphic recording of the Responsive talk was republished a month later in a sketchnote roundup, which belongs on the artifact's own entry. And same when a company account publishes something its founder already posted: Wunderdogs' 10-26 interview post looked like a clean new entry but covered the conversation Daria Gonzalez had posted herself on the 23rd — a different post about the same thing, which the source_url grep cannot catch and only reading does. thoughtbot's 10-28 post for the Giant Robots episode is the same shape.

DEPTH CAN CARRY AN ENTRY WITHOUT PRAISE (Eric, 2026-10-19). A substantive argument that uses the book — even at 2-3 reactions — ships. The Christopher Marquis NYT op-ed on shutting down business schools has now pulled three separate people into citing Incorruptible as the answer. Michael Kobori naming it as the influence on his own governance series is the same shape, as is Mo Salah reading Red Bull's engine programme through it at zero reactions, and Logan Yonavjak's "structure constrains bad leaders without necessarily producing good ones" — a disagreement that engages rather than dismisses. Dan Barker's 2026-10-22 post is the pattern for a reader finishing: his first two entries were mid-read reactions, and the third took the argument somewhere new, against the economics of AI. Nick Hague on 10-26 is the pattern for a reader supplying evidence: he states financial gravity correctly and then gives his own case, "When I sold my agency, the culture began to shift... Decisions that would have taken five minutes now took five months." Sebastian Ross on 10-27 is the pattern for a SECOND entry from the same person being justified: his June entry was a recommendation, this one brings a 250,000-founder study showing 88% end with zero exit value and lands on "Governance rules and term sheets are the point of attack." The inverse also holds, and it recurs: Martin Aguinis's full-circle story was the highest-engagement post of 2026-10-22 at 54 reactions and was skipped because it is entirely about The Lean Startup, Alejandro Pinzon's (27 reactions, top post of 10-23) for the same reason; and Ronei Vinagre's on 10-26 at 293 reactions — the biggest of the week by far — because it is a Portuguese reading list naming A Startup Enxuta. Engagement does not convert a Lean Startup story into an Incorruptible one.

A warm reply from someone already heavily represented is archive material, not a sixth entry. Bob Sutton on 2026-10-24 — "I am starting to think you are  Inexhaustible!" — is a lovely line from a Stanford professor with 73K followers, and it was still a skip: encouragement rather than a new argument, from a man with five entries already. Ask what the post ASSERTS, not how notable the poster is.

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

### Foreign editions — every one, on its own publication date

Eric, 2026-11-01: *"please include all foreign editions (tied to their publication
date), track as they come up. fine to post in english announcing it but also include
foreign-language material from the publisher when available. note translator as well
as publisher."*

So each translation is its own entry, `type: media`, **dated the edition's own
publication date** — not the day it was found. The German edition published on
2026-08-16 and was only noticed on 11-01; it is dated August.

- **Title and summary in English.** The entry announces the edition to an
  English-speaking timeline.
- **Blockquote is the publisher's own copy, in the original language**, when the
  publisher has any — attributed to the publisher, never to Eric. Verify it on the
  publisher's own page, not a retailer's: retailers list the English edition under
  local ISBNs constantly and look like translations in search results.
- **Name the translator as well as the publisher.** Both go in
  `attribution_title`, and in `type_metadata` as `language`, `translator`,
  `publisher` so the set is queryable later.
- **Cover art** to `/images/events/`, with `image_fit: contain` and an
  `image_bg` sampled from the jacket.

Known so far: German — REDLINE Verlag (Münchner Verlagsgruppe), trans. Jordan
Wegberg, 2026-08-16. Spanish — *Incorruptibles*, Deusto (Grupo Planeta), trans. Eva
Morón, 2026-11-25. The Goodreads editions page is the cheapest enumerator
(`/work/editions/266561646-...?per_page=100`); it renders server-side and lists
publisher and date per edition, which is how the German one surfaced. Re-check it
periodically — translation deals land without announcement.

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

**The quote gate is offline-first, and SAVING THE SOURCE TEXT is the job.** The
pre-commit hook runs `python3 scripts/quote_integrity.py` on changed entries: it
checks the blockquote against `data/archive/source-texts/<entry-id>.json`, which
is the only check that works on LinkedIn and X — 62% of entries, which no
anonymous fetch can read. `--require-capture` fails the commit for a NEW entry
that has none. Write the capture as you ship, with `entry_id`, `source_url`,
`platform` and `full_text`.

Why this is a hard rule rather than a nicety: before 2026-10-28 the verifier
checked **25 of 871 entries and exited 0**, because `verify-quotes.ts` skipped
anything carrying `verified: false` and the hook's own failure message advertised
setting that flag as the way to make a failing check pass. 725 entries took the
hint. **Never set `verified: false` to silence a check** — the skip is gone and
the field is inert, but the habit is the bug. See
`docs/postmortems/2026-10-28-the-quote-gate-verified-three-percent.md`.

Read the verdicts carefully, because three of the six are not failures:

| verdict | meaning |
|---|---|
| `exact` / `normalised` | verified; `normalised` means byte-level drift (smart quotes, dashes, a newline joined) |
| `partial` | **the composited-quote signature** — the opening is real and the rest is not. 14 were found and repaired on 2026-10-28 |
| `absent` | the quote is not in the captured document |
| `no-source` / `source-mismatch` / `medium-mismatch` / `weak-capture` / `comment-mismatch` | could not be checked, NOT a pass — a capture of the wrong url, a transcript judged against show-note copy, a scraped page that was only nav, or a post capture judged against a quote taken from its comments |

If you trim a quote, mark the cut with ` … `. `scripts/repair_elisions.py` does it
mechanically and refuses unless every segment is verbatim AND in source order;
the checker then verifies `A … B` segment by segment. **Both** checkers do — the live one
did not until 2026-10-31, and for three days reported all 23 elided entries as
composites. A new matching convention goes in `data/quote-match-cases.json`,
which `tests/quote-match.test.ts` and `scripts/test_quote_match_cases.py` both
load, so teaching one language and not the other fails the other's tests. A bad capture is worse than
none — never store a bare domain root, because the homepage served today is not
the page the entry quoted months ago.

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

## 7. Sourcing a face

Moved here from the evening-scan prompt on 2026-11-08, verbatim. The morning-scan
prompt carries a near-identical copy of this block; two copies of one rule diverge,
so both prompts should point here instead (memory/feedback_one_rule_one_implementation.md).

Also: pick 2-3 unimaged older entries from the backlog and source photos. Query with BOTH image and attribution_image null. RUN `python3 scripts/find_ondisk_images.py` FIRST — it reports unimaged entries whose headshot is already in public/images/people/, `--wire` attaches the unambiguous ones, and rejected matches go in data/ondisk-image-skips.json with a reason so they stop reporting. It found six in two days before it was a script. The LinkedIn avatar archive gives zero matches for the old entries and YouTube thumbnails are exhausted, but the web is NOT dry for named executives — speaker bureaus (speakabout.ai og:image, 1000x1000) and company newsrooms carry clean headshots, which is how Tatyana Mamut and Carolyn Groobey were sourced, and Madeline McIntosh from a Lee Enterprises board-director profile. Wikimedia Commons is worth a try for anyone with a Wikipedia page — Garry Tan on 2026-10-23, and Roy Bahat on 2026-10-24 from a file literally named "Roy Bahat, head of Bloomberg Beta", matching the entry's own attribution_title. A company team page can work where its og:image does not: Chike Aguh came from kaporcenter.org on 2026-10-25, but only the uncropped original was usable — the 640x360 derivative the page linked cut his eyes off. A conference speaker page is another reliable route: Dee Coakley came from a Startup Grind Dublin event page on 2026-11-01 whose og:image was a Cloudinary-resized headshot, and Elizabeth Solomon from her publisher's author page. Confirm a profile page is the same person before using its photo. Order to try: find_ondisk_images.py, speaker bureau, Wikimedia, company newsroom or about page, conference speaker page, fellowship/award bio, personal site. Square-crop with `sips -c <h> <h>` then resize to 600, then LOOK at the result before wiring it. Stop when the name is ambiguous across several people — no image beats a wrong face, and "no new image found" is a fine answer; David Bland and John Paul Farmer both came up dry on 2026-10-23, Farmer again on 10-24, and SkyDeck and Vistage on the 25th, Sri Rajan, Marsha Acker and Sasha Orloff on the 26th, and Ann Armbrecht and the Fourth Effect on the 27th, Courtney Sung and Clark Freifeld on the 28th, and the Corporate Rebels Summit on 11-01. Added 2026-11-07/08: Michael McKinney (LeadershipNow's only photo is a 300x160 speaking shot), Michelle McDaid (The Leading Place serves its FAVICON as og:image), Rob Runett (the Motley Fool Ventures team page no longer lists him), Marsha Acker (her own site returns a near-empty page) and Ed Barker (studio1878 does not resolve on any TLD tried). Michelle Hirons is not on HigherRing's team page either. Do not re-try these without a new lead. Added 2026-11-09 and RESOLVED 2026-11-12: Jyoti Guptara. jyotiguptara.com does not resolve, but his site is guptara.com, and its about page carries a studio headshot — the dry note had recorded a guessed domain as a dead end rather than the one place the name actually points. Strip the WordPress size suffix for the original: the linked variant was 200x260, the unsuffixed file 1120x1680. Mark Goyder got his entry on 2026-11-11 and find_ondisk_images wired mark-goyder.jpg to it exactly as that note predicted — the on-disk index paying off two days after the file was saved for an entry that did not need it. Identity was re-confirmed against the Wikimedia photo of him receiving an honorary doctorate at UEA before wiring, because the script asks you to confirm a file's first use. Added 2026-11-11 to the dry list: Ryan Davies (mckinsey.com/our-people/ryan-davies times out at 60s, tried twice on consecutive days; a UA-spoofed curl is refused by the sandbox and should not be attempted), Tom Elmer (his only photo is a side-on lectern shot with a microphone in frame; cropping tighter made it worse, so his entry keeps its quote card) and Nick Hague (worldsgreatestbusinessthinkers.com serves a video still as og:image). Two that DID work the same day, both from a dedicated profile page rather than a share card: Christopher Parsons from knowledge-architecture.com's about page — which carries TWO Parsons, so the page text was read to confirm which one is Founder and CEO before wiring, not just the filename — and Liba Wenig Rubenstein from nexusproject.us/individuals/.) Org and event logos go in /images/events/ — there is no /images/orgs/. Reject og:images that are grids of other people's faces or generic sitewide share cards: Goodword's, Interintellect's salon banner, the American Botanical Council logo standing in for Ann Armbrecht, the Fourth Effect's social-preview.jpg, and the Corporate Rebels Summit page whose og:image is three other speakers' faces were all that shape. Reject an avatar that is not a headshot at all: Stephanie Pierucci's on 10-28 was a mocked-up Business Insider cover carrying the real masthead, which would read on the timeline as genuine BI coverage. AFTER attaching any image run `npm run build && python3 scripts/check-images-render.py`, which reports entry image paths reaching no HTML.
