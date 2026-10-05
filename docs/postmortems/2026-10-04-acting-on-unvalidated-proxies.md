# Postmortem — acting on unvalidated proxies (2026-10-04)

Four incidents over roughly a week look unrelated. They have one root cause.

In each case a **proxy** stood in for the real thing — a truncated slice for a
post, a capped query for a week's recall, an old timing claim for a hook, a
character count for a token count — and the proxy was trusted without anyone
checking that it still represented what it claimed to.

---

## Incident 1 — a shippable entry dismissed as a word collision

**What happened.** During the 2026-10-04 comment-archive scan, Paige Kaye's post
matched the book-anchor gate. I printed the first ~420 characters to decide
whether it was relevant. The opening used "incorruptible" as an ordinary
lowercase adjective ("a long-term vision to build an incorruptible company"), so
I classified it a false positive and reported it as such. Eight lines further
down — outside the slice — she writes: *"(Eric Ries's book "Incorruptible" is a
big inspiration of mine and reminds me that I can eat glass a little longer
until I identify the right investors/partners for PaigeKares)"*. It only
surfaced because Eric happened to ask about a different commenter on that thread.

**Five whys.**
1. Why was it dismissed? The visible text showed only adjectival use.
2. Why was only that text visible? The triage dump truncates to ~400 chars.
3. Why decide from the triage dump? It was already on screen and reading more
   meant another tool call.
4. Why did that feel acceptable? Truncation had been harmless for *ranking*
   candidates, so I carried it into *deciding* them without noticing the shift.
5. Why wasn't the shift noticed? Nothing in the process distinguished "cheap
   view for sorting" from "complete view for judging" — same output, two jobs.

**Root cause.** A display convenience was silently promoted into an evidentiary
standard.

**Aggravating factor specific to this project.** People routinely use
"incorruptible" as a plain adjective *before* crediting the book later in the
same post. The top of a post is precisely where the evidence is least likely to
be. The truncation was not merely lossy, it was biased against the signal.

**Fix.** `scripts/scan-triage.py --full <N>` prints an item entirely, never
truncated, and the table footer advertises it on every run. Memory:
`feedback_read_whole_parent_post.md`.

---

## Incident 2 — a peer-tier endorsement never reached the daily scan

**What happened.** Raj Sisodia — co-founder of the Conscious Capitalism
movement, 16 books — posted "Eric Ries's exceptional and essential book
'Incorruptible'". No daily scan surfaced it. The weekly recall audit caught it.

**Five whys.**
1. Why did the daily scan miss it? The production query `"Incorruptible Ries"`
   did not return the post.
2. Why not? LinkedIn multi-word search is not a reliable AND over post text —
   the post contains *both* terms and was still not returned.
3. Why was that unknown? Previous audits reported no drift.
4. Why did they report no drift? They ran at `maxPosts=40`, where both the
   production and comparison queries hit the cap. Two truncated lists overlapped
   heavily, which reads as agreement.
5. Why did a capped comparison look like a clean one? The audit reported overlap
   percentages without reporting that both inputs were cap-limited.

**Root cause.** The instrument built to detect recall loss was itself
recall-limited, and reported confidence it had not earned.

**Fix.** Audit now runs at `maxPosts=100` (production returned 63 — comfortably
clear of the cap, so the comparison is real). Morning scan runs a second bare
`"Incorruptible"` query, manually filtered. Memory:
`feedback_linkedin_query_calibration.md`.

---

## Incident 3 — duplicate entry written before the duplicate check ran

**What happened.** A Brian Behm review was researched, written, imaged and
quote-carded before I noticed — at `git add`, from the image path showing as
*modified* rather than *added* — that he had shipped two days earlier with a
stronger quote. The entry was pulled.

**Five whys.**
1. Why was duplicate work done? The author check happened after writing.
2. Why after? There was no check in the triage step at all.
3. Why not? Dedupe was conceived as a *correctness* gate (don't publish twice),
   and correctness gates live near commit.
4. Why is that wrong? Duplication is primarily a *cost* problem — the expensive
   part is the research that precedes the entry.
5. Why wasn't that noticed? The commit-time gate did eventually prevent the bad
   outcome, so it looked like it was working.

**Root cause.** A gate placed where it prevents the error rather than where it
prevents the waste.

**Fix.** `scan-triage.py` flags `SHIPPED` and `AUTHOR-HAS-N` inline in the
triage table, with entry ids, before any research begins. Memory:
`feedback_check_person_already_shipped.md`.

---

## Incident 4 — a stale performance claim steering the process

**What happened.** The cron prompts state the pre-commit hook "takes ~3–5
minutes on 760+ entries" and instruct a 420,000 ms commit timeout. Measured
today: lint 0.33 s, vitest ~1 s, verify-quotes 10.3 s. **The hook takes about
12 seconds.**

**Five whys.**
1. Why is the claim wrong? It was true when verify-quotes fetched every source
   page over the network.
2. Why is it no longer true? 759 of 785 entries are `verified: false` and skip
   the fetch entirely.
3. Why didn't the claim get updated? It lived in a cron prompt, not in code.
4. Why does that matter? Code drifts loudly (tests fail); prose claims drift
   silently.
5. Why was it never re-measured? Nothing ever prompted a re-measure — it was
   never wrong in a way that hurt.

**Root cause.** Performance facts recorded as prose have no expiry and no test.

**Impact.** Low in itself (an over-long timeout is harmless), but it discouraged
frequent small commits and it masked the signal value of a genuinely slow
commit.

**Fix.** Claim corrected in the cron spec. Where a number steers behaviour, it
should carry the date it was measured.

---

## Incident 5 — this very analysis, nearly

While measuring token costs for this reflection, I first ranked `Read` as the
single largest consumer: 174 image reads at ~121,000 characters each, apparently
~5.2M tokens, dwarfing everything else. I was about to design a contact-sheet
batching system around it.

That number was wrong. Images sit in the transcript as base64, but their cost to
the model is the image-token formula (roughly `w×h/750`, capped near 1,600),
not `characters/4`. Correctly computed, all 203 images cost **at most 0.32M
tokens** — about 4% of tool traffic, not 67%.

**Five whys.**
1. Why was the estimate wrong? One heuristic (`chars/4`) was applied to a
   payload type it does not describe.
2. Why was it applied anyway? It was the convenient uniform metric across tools.
3. Why wasn't the mismatch obvious? Base64 is text-shaped, so it passed through
   a text-shaped measurement without complaint.
4. Why did that nearly cause harm? The ranking it produced was not just
   imprecise, it was *inverted* — it pointed at the cheapest major tool.
5. Why was it caught? The per-call average (121,000 chars for a headshot) was
   implausible enough to prompt a second look.

**Root cause.** Same family as the rest: a proxy adopted for convenience, then
trusted outside its domain.

**The lesson that generalises.** When a measurement is going to drive a
decision, confirm the unit describes the thing. The tell here was an implausible
magnitude — treat "that seems like a lot" as a reason to re-derive, not to act.

---

## What actually changed

| Proxy | Was trusted as | Now |
|---|---|---|
| 400-char triage slice | the post | `--full <N>`, advertised every run |
| `maxPosts=40` audit | the week's posts | `maxPosts=100`, headroom verified |
| commit-time dedupe | enough | `SHIPPED` / `AUTHOR-HAS-N` at triage |
| "3–5 min hook" | current | measured at ~12 s, corrected |
| `chars/4` | token cost | per-payload-type accounting |

## The standing rule this produces

**A summary may rank; only the source may decide.** Anything that compresses —
a truncated slice, a capped query, a cached timing, a convenient unit, and
notably *a subagent's prose summary* — is fit for sorting candidates and unfit
for settling them. Where a compressed view is used to decide, the full form must
be one obvious step away, and that step must be advertised at the point of
decision rather than remembered.
