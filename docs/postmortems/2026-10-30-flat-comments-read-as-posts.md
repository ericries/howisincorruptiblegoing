# A comment read as a post, and a count that counted the loop variable's name

**Date:** 2026-10-30
**Found by:** Me, mid-classification, while trying to read the parent post for
three candidates whose `parent_post` was empty. I inferred the parent wrongly
**twice** before finding the field that actually resolves it. Eric then asked
for the five whys.

## What happened

`harvestapi/linkedin-post-search` with `scrapeComments: true` represents every
comment **twice**: nested under its post as `post["comments"]`, and again as a
flat top-level sibling carrying `postId`. Measured on the 2026-10-30 author
pull:

```
total items                         250
  with an `author` key (posts)       40
  without one (flat comments)       210
comments nested inside those posts  210   <- the same 210
posts carrying a nested array        37
```

`queue_from_posts` iterates `for post in items` and treats **every** top-level
item as a post. The 210 flat siblings therefore fell into the post branch,
which sets `"parent_post": None`. Both representations produce the same
`_stable_identifier`, and the queue dedups by identifier keeping the first
seen — and the stream begins with a comment (`cPcPcccc…`), so the parentless
record normally won and the nested record that knew its parent was discarded.

Result: **34 of 247 candidates had no parent_post**, and **three of the nine
records archived that day went to disk without one** — Michael Paradise and Tim
Olaore (both on David Banks's AdventHealth post) and Diederick Janse (on Pim de
Morree's Corporate Rebels post).

Separately, the progress line read **"Scanned 250 posts / 210 comments"** for a
pull containing 40 posts.

## Five whys

**1. Why was `parent_post` empty on 34 candidates?**
They entered the queue through the branch that treats a top-level item as a
post, and that branch hard-codes `"parent_post": None`. They are comments.

**2. Why did comments go through the post branch?**
The loop assumes one shape — a list of posts, each with its comments nested —
and the actor emits a different one: a flat interleaved stream in which the
nested arrays are duplicated as siblings. Nothing in the loop distinguishes the
two kinds of item, so the flat comments were simply called `post` and treated
accordingly.

**3. Why did the broken record beat the good one?**
Because dedup is by identifier and keeps the first occurrence, and the flat
comment is usually encountered before its post. The dataset's own ordering
decided which version of each comment survived. That is a coin-flip the code
never knew it was making.

**4. Why was it not caught?**
Nothing asserted the shape of what was being iterated, and the one number that
would have revealed it was not a measurement. `scanned_posts += 1` inside
`for post in items` reports the length of the list; it said "250 posts" for 40
and nobody blinked, because a progress line is read as reassurance rather than
as data. Downstream, a missing parent is invisible: an empty `parent_post`
field at classification time looks exactly like a comment that never needed
context, rather than one whose context was thrown away.

**5. Why does this class keep recurring?**
This is the third time in three days that **a number derived from an assumption
was reported as though it had been observed**. The item cap reported items and
was read as posts. The quote gate reported passes and was read as coverage.
Here the counter took its meaning from the loop variable's *name*: the loop
calls everything `post`, so the counter counts posts. In each case the code
stated its own assumption back to me in the shape of a measurement, and I
believed it because it arrived as a number.

## Prevention, proportional at each level

| why | prevention | kind | status |
|---|---|---|---|
| 1 — the instance | The three archived records repaired in place, parents resolved via `postId` — Banks, Banks, de Morree, matching what I had worked out by hand | fix | shipped |
| 2 — the local condition | `is_post()` routes each top-level item by its shape (`author` present), and flat comments go to `_queue_comment` with their post looked up from a `posts_by_id` index built before the loop — so a comment arriving before its post still resolves | fix | shipped |
| 3 — the ordering coin-flip | Both representations now carry the parent, and when the second arrives it back-fills the parent onto an already-queued record rather than being dropped. `test_flat_first_still_yields_a_parent_post` and `test_nested_first_also_yields_a_parent_post` pin both orders, so arrival order can no longer decide what survives | test | shipped |
| 4 — why it wasn't caught | `count_by_shape()` measures posts and comments from the data, and the queue builder prints a loud `WARNING: N comment(s) have an unresolved parent post` naming the missing `postId`. A record that cannot resolve its parent now keeps `parent_post_id`, so it says *which* post is missing instead of looking like a comment nobody needed context for | mechanism | shipped |
| 5 — the system | Two regression tests run against the real 2026-10-30 pull — `test_real_pull_resolves_every_parent` (34 orphans before, 0 after) and `test_real_pull_counts_posts_correctly` (asserts 40, not 250). The payload's dual-representation shape is now pinned by a fixture that documents it, so the next person reads the shape instead of inferring it from a variable name. 12 tests in `scripts/test_queue_shape.py` | structural change | shipped |

Verified end to end: the live script now prints `Scanned 40 posts / 210
comments`, the orphan warning fires when posts are withheld, and the full suite
is 341 green.

## Open items

**The identifier is doing two jobs.** `_stable_identifier` is both the dedup key
and the archive's primary key, which is what made the two representations
collide silently rather than merge. The merge is now explicit in
`_queue_comment`, but a record shape that distinguished "same comment, second
sighting" from "new comment" would not have needed one. Not worth the churn
today; worth knowing if this bites a third time. **Open.**

**`text` is not stored on archived records**, which is why repairing them had to
match on identifier rather than content. That is probably correct — the archive
keeps `pull_quote`, not the full comment — but it means any future repair is
identifier-only, and an identifier change would orphan the record permanently.
**Open.**
