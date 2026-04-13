# Postmortem: Fabricated Blockquotes in Timeline Entries

**Date:** 2026-04-12
**Severity:** High — 7 of 45 entries had quotes not present at their source URLs
**Fixed in:** commit 5ed29e4

## What happened

During initial content seeding, a research subagent searched the web for Incorruptible coverage and reported "key quotes" for each find. These quotes were placed directly into entry JSON files as `blockquote` values. 7 of the quotes were paraphrased, composited from multiple sentences, or entirely fabricated by the LLM — they did not appear at the linked source URL.

## Five Whys

1. **Why did entries have fake quotes?** The research subagent reported paraphrases and summaries as if they were exact quotes.
2. **Why were these trusted without verification?** Speed optimization — entries were batch-created from the research report without fetching each source.
3. **Why wasn't there a verification step before committing?** The quote verification tool (`verify-quotes.ts`) didn't exist yet. The review bot only runs in GitHub Actions on PRs.
4. **Why were entries committed directly to main?** The PR pipeline was designed for the automated scanner, not manual seeding. The initial buildout bypassed it.
5. **Why didn't the process enforce verification regardless of entry method?** The pre-commit hook only checks schema/injection (fast, no network). There was no local quote verification step.

## Preventive measures installed

1. **Created `scripts/verify-quotes.ts`** — fetches each entry's source_url and checks that blockquote text appears on the page. Distinguishes full matches, partial matches, and failures. Handles LinkedIn/Twitter/endorsement skips gracefully.
2. **Updated CLAUDE.md** — added explicit rule: "Blockquotes must be EXACT text. Never trust LLM-reported quotes. Run verify-quotes.ts before committing."
3. **Process rule:** When creating entries from research, always fetch the source page independently and copy the exact text. Never use the research agent's reported quotes verbatim.

## Root cause

LLM hallucination in the research → content pipeline. The research subagent's job was to find URLs and summarize content, but its output was treated as a source of exact quotes. LLMs are unreliable quoters — they paraphrase by default.

## Lesson

Any text attributed to a specific source must be verified against that source before publishing. "The LLM said this is on the page" is not verification.
