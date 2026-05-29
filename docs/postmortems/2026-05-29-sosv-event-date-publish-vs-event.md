# 2026-05-29 — SOSV event entry dated wrong (publish date used as event date)

## What happened

Shipped `2026-05-12-sosv-deep-tech-live-po-bronson.json` for the SOSV Deep Tech
Live event with Po Bronson moderating. Used `date: "2026-05-12"`. Actual event
is **Thursday, June 11, 2026, 3:00–5:00 PM PDT**. User caught it after the
entry was already pushed and rendered in the timeline + book-tour strip.

## Five Whys

1. **Why was the date wrong?** I used "May 12, 2026" from the SOSV article page
   as the event date.
2. **Why?** WebFetch's summary returned `Date and Time: May 12, 2026 (specific
   time not provided)` and I treated it as authoritative.
3. **Why was the summary wrong?** May 12 is the SOSV article's **publish date**;
   the actual event datetime lives on the linked Luma RSVP pages, not the
   marketing article. The summarizer grabbed the most prominent date string.
4. **Why didn't I cross-check?** I had `source_urls` pointing to two Luma RSVP
   pages but didn't fetch them. For events, the registration page is the
   canonical datetime source.
5. **Why no rule for this?** Existing rules cover quote verification but not
   event-date verification. This failure mode hadn't surfaced before.

## Signal I ignored

The summary said `(specific time not provided)`. A legitimate event listing
always has a time. The absence should have been a flag that the date came
from elsewhere on the page (the masthead).

## Preventive action

1. New memory rule `feedback_event_dates.md`: for event entries, confirm
   date/time on the RSVP/registration page (Luma, Eventbrite, host's event
   page) — not just the announcement article.
2. Heuristic: if no time appears alongside the date, the date is suspect.

## Out of scope / not added

- No lint check (would require fetching external URLs at lint time).
- No automated cross-source date diff (too brittle).
