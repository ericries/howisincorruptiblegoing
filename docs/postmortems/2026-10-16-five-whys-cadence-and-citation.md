# Five Whys — October 2026: cadence assumptions and unverified citations

Five incident threads from 2026-10-03 → 2026-10-16. Each is traced to a root
cause and, where one existed, a preventive measure installed in code rather
than in a prompt. Prompts drift; lint does not.

---

## Thread 1 — High-signal posts went unseen for four days

**Incident.** The Oct 12 evening @-mention scan never ran. Three posts —
108, 81 and 68 reactions, including The Secret CFO's second endorsement —
surfaced only on Oct 16 when a human asked whether anything had been missed.

1. *Why were they missed?* The Oct 12 scan did not run.
2. *Why did nobody notice?* The commit log looked healthy for Oct 12.
3. *Why did it look healthy?* Other cycles ran that day and committed.
4. *Why was the commit log the health signal?* The watchdog's sanity check was
   `git log --since="36 hours ago"`.
5. **Root cause.** We monitored **output**, not **coverage**. Output proves
   *something* ran; it can never prove *everything* was attempted.

**Installed.** `scripts/scan-coverage.py` — per-source, per-day coverage from
the archive, run first by the watchdog. Against the real archive it reports
exactly the two known gaps and no false positives.

**Second-order fix.** Detection is not prevention. `scan_state.choose_posted_limit()`
derives the window from the last successful scan, so a missed day widens the
next pull instead of being skipped past.

---

## Thread 2 — A shippable review was skipped from a 13-item list

**Incident.** Fora Fereydouni (Founder & CEO, Cognitai, 47 reactions) sat in an
Oct 6 daily list of thirteen items and was passed over. The weekly audit
shipped her five days late. The same failure mode nearly lost Paige Kaye.

1. *Why was she skipped?* The decision was taken from the truncated triage row.
2. *Why from the row?* That is what `scan-triage.py` prints.
3. *Why does it truncate?* Token efficiency — the deliberate design.
4. *Why does truncation lose entries?* People open with a generic hook and
   credit the book several paragraphs down, below the cut.
5. **Root cause.** The tool economises at precisely the point where spending is
   warranted — the ship/skip decision — and leaves "read the full text" to
   human discipline, which fails under volume.

**Proposed, not yet built.** A `BELOW-FOLD` marker on rows where the book
reference appears *after* the truncation point. That is mechanically detectable
and converts a discipline problem into a flag. Deferred because it changes
triage output that several prompts depend on; worth doing deliberately.

---

## Thread 3 — A fabricated URL was written into an entry

**Incident.** On 2026-10-16 an entry was authored with
`.../activity-7515320000000000000-xxxx` as its `source_url`. Caught by eye
before commit.

1. *Why was a placeholder written?* The real URL was not to hand.
2. *Why not?* The post had been read via `--full` at a different dataset index,
   and the URL was not captured with the text.
3. *Why proceed anyway?* Three entries were being written in one batch script;
   stopping to fetch would have broken the batch.
4. *Why is that acceptable-feeling but dangerous?* A fabricated citation is
   indistinguishable from a real one at review time and would ship silently.
5. **Root cause.** CLAUDE.md's rule — *never create an entry you cannot source*
   — had **no enforcement point**. It lived only as an instruction.

**Installed.** `src/lib/source-url-integrity.ts` → `looksFabricated()`, wired
into lint as a **hard failure**. Catches placeholder tokens and
implausibly-padded platform ids. 9 tests.

---

## Thread 4 — Duplicate entries persisted unnoticed

**Incident.** Three entries on `thoughteconomics.com/eric-ries/`, two
near-identical. Flagged on Oct 11, still unresolved Oct 16. A second pair
(Boardy Substack, Apr 20 and Apr 21, same article, same opening quote) was not
noticed at all until the new check found it.

1. *Why were duplicates created?* Different cycles on different days.
2. *Why did dedup not catch it?* `scan-triage.py` marks `SHIPPED` by matching
   against the repo — but only for items present in the dataset being triaged.
3. *Why is that insufficient?* An entry created last month is not in today's
   dataset, so the collision is invisible.
4. *Why was there no repo-wide check?* Dedup was treated as a scan-time
   concern, not a repository invariant.
5. **Root cause.** The check lived at the wrong layer — dataset-scoped rather
   than repo-scoped.

**Installed.** `findDuplicateSourceUrls()` in lint, as a **warning** (an event
entry and its reaction may legitimately share a source). It immediately found
the Boardy pair that manual inspection had missed. Known-shared canonical URLs
(`incorruptible.co`, the Amazon product page) are allowlisted.

---

## Thread 5 — A rule was followed wrongly for days

**Incident.** Reactions were capped at five per parent. The cap did not exist.

1. *Why was it applied?* `memory/feedback_reactions_editorial.md` said "3-6".
2. *Why did the file say that?* Its one-line `description:` said it; the body
   said "6-10 feels rich" and "LEAN GENEROUS".
3. *Why did the description win?* Descriptions load into context every session;
   bodies load only on recall.
4. *Why did they diverge?* The body was revised; the description was not.
5. **Root cause.** The description is the **de-facto rule** but is authored as
   a summary, so it drifts silently from the body it summarises.

**Installed.** Description corrected. A drift audit across all memory files
(comparing numeric claims in description vs body) found no other instances.
Standing practice: when revising a memory body, re-read and reconcile its
description.

---

## Open, requiring Eric's decision

- Merge the Thought Economics duplicates (keep the May 29 entry, which pulls a
  different quote; the May 21 pair are the same piece).
- Merge the Boardy Substack duplicates.

Both are entry deletions, which are irreversible and editorial.

## Open, not yet addressed

- **The event pipeline thins after Nov 4.** Nothing scheduled beyond SOSV.
  What's New depends on upcoming events; in ~3 weeks it has only endorsements
  and milestones to draw on.
- **`scan_state` is instructed, not enforced.** The cron prompts tell the
  scanner to derive `postedLimit`; the Apify calls still go through a human-in-
  the-loop step that can skip it. Folding window selection into
  `scan-triage.py` would make it structural.
