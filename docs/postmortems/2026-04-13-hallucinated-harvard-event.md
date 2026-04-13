# Postmortem: Hallucinated Harvard Book Store Event

**Date:** 2026-04-13
**Severity:** High — published a fabricated event to the live site
**Fixed in:** commit 985c000

## What happened

A WebSearch result returned a link to harvard.com/event/eric_ries/ mentioning "Eric Ries" and "Eisenmann." The page was JS-rendered and returned no readable content. Instead of stopping, I assumed the event was for Incorruptible and created an entry using Eisenmann's existing endorsement quote (not text from the Harvard page). The event may have been for The Startup Way (2017), not Incorruptible.

## Five Whys

1. **Why was the entry created?** WebSearch returned a plausible-looking result and I assumed it was real.
2. **Why assume instead of verify?** The page was JS-rendered and unreadable. I filled in gaps with assumptions.
3. **Why wasn't unreadable page a stop signal?** No rule explicitly said "don't create entries for unreadable pages." The bias was toward action (add content) over accuracy.
4. **Why didn't safeguards catch it?** The blockquote was Eisenmann's endorsement (already known), so linting passed. Quote verification against the Harvard URL would have failed, but it wasn't run.
5. **Why wasn't quote verification run?** It's a manual step. The pre-commit hook didn't include it.

## Root cause

Same pattern as the first postmortem: **creating entries from unverified sources.** This time it was a search result snippet rather than an LLM research report, but the failure mode is identical — acting on information that hasn't been independently confirmed by reading the actual source page.

## Preventive measures

1. **Updated CLAUDE.md** with two new critical rules:
   - Never create an entry if you cannot read the source page
   - Search result snippets are not evidence
2. **Pre-commit hook now runs verify-quotes.ts** on all changed entry files. The commit would have been blocked because the Harvard URL would have failed quote verification.
3. **Process rule:** If WebFetch returns no readable content for a URL, that URL cannot be used as a source.
