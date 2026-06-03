# Postmortem — Apify MCP "down" wasn't down (stale-session misdiagnosis)

**Date:** 2026-06-03
**Trigger:** This morning's content scan kicked off three Apify actor calls in parallel; all three returned `Streamable HTTP error: Error POSTing to endpoint: ... Session ID 64f11f78-08ac-4dca-93fa-3de6d54f9a5d not found`. I reported "Apify session disconnected" and fell back to WebSearch for the morning scan. The user ran `/mcp` once — got "Reconnected to apify" — and asked why this keeps happening.

The Apify service was never down. My session token had expired, and I treated that as a service outage.

## Five Whys

1. **Why does Apify appear to be down when it's really not?**
   Because my Apify tool call returns `Session ID ... not found` and I read that as "Apify is unavailable" — when in fact only my session token has expired; the Apify server is fine. The `/mcp` reconnect immediately makes the same call work.

2. **Why do I interpret a "session not found" error as a service outage?**
   The error wraps the server response in a generic `Streamable HTTP error` framing, and my heuristic for tool errors lumps all non-zero exits into "the tool isn't available." I don't distinguish between (a) the service is unreachable, (b) my session token is stale and needs refresh, (c) the actor itself errored. All three look the same, so I default to the most conservative response — assume unavailable, switch to fallback.

3. **Why don't I have a recovery mechanism for stale session IDs?**
   The only way to re-handshake an MCP session is through the user-facing `/mcp` slash command. I can't initiate that handshake from inside the conversation; the runtime exposes the tools but not the session-management primitives. Retrying the same actor a second time just hits the same stale session — retry alone doesn't help.

4. **Why didn't this signal get captured anywhere durable so future-me would recognize it instantly?**
   Each time it happened I treated it as a one-off transient and wrote no memory. Worse: `project_scanner_crons.md` has an "Apify-down fallback" section that *reinforces* the wrong mental model — it tells me what to do when Apify is unavailable, not how to first check whether the failure is actually a recoverable stale-session problem. So the pattern keeps recurring.

5. **Why does this matter — what's the cost?**
   Direct: every misdiagnosis means a degraded scan (WebSearch fallback yields ~10% of normal output per the memory), so missed entries and weaker reports. Indirect: the user has to notice, type `/mcp`, and re-issue the prompt — friction they shouldn't have to absorb. Over many scans this compounds into a real gap between what I ship and what I could ship.

## Root cause

The string `Session ID ... not found` (and its `Streamable HTTP error: Error POSTing to endpoint` wrapper) is a **recoverable handshake problem**, not a service outage. It surfaces through the same error channel as service outages, and I had no pattern to distinguish them and no way to recover from the recoverable case on my own.

## Preventive measures

1. **New memory `feedback_mcp_stale_session.md`** codifying the signal:
   - The substring `Session ID ... not found` or `Streamable HTTP error: Error POSTing to endpoint` = stale MCP session, not an outage.
   - The fix is the user running `/mcp`. Do not silently switch to WebSearch.
   - Pause and ask the user to `/mcp`, then re-issue.

2. **Updated `project_scanner_crons.md` fallback gate.** The "Apify-down fallback" section now requires a real outage diagnosis (MCP server missing from session reminders, or multiple distinct actor names returning genuine network errors) — not a session-ID error.

3. **Behavioral change.** When I see this exact error pattern, tell the user: *"Apify MCP session looks stale — can you `/mcp` to reconnect? I'll wait."* rather than burning the turn on degraded fallback.

## Detection signal (future-me, read this)

If you see ANY of these, it is almost certainly a stale session, not a real outage:
- `Streamable HTTP error: Error POSTing to endpoint`
- `Session ID <uuid> not found`
- All three parallel actor calls fail identically with the same session UUID

A real outage looks like: timeouts (no response at all), actor-level errors (`actor not found`, `input validation failed`), or the MCP server being absent from the session-start MCP list. None of those mention a session ID.
