# Amazon customer review archive

Snapshots of the Amazon customer reviews page for *Incorruptible*. Future agents reading this directory should use these snapshots to:

1. Skip reviewers already shipped as entries (`shipped_as_entry_id` is set if so).
2. Identify high-signal reviewers (notable authors, large helpful counts, format = Verified Purchase, multi-paragraph reviews) for new entries.
3. Track review velocity and rating distribution over time.

## Files

- `YYYY-MM-DD.json` — one snapshot per day the reviews are captured. Each file holds the page-level metadata (totals, star distribution, snapshot timestamp) plus every review parsed from the page.

## Source

Amazon page (logged-in): https://www.amazon.com/Incorruptible-Good-Companies-Great-Stay/product-reviews/B0FWZZBPZB/

Reviews are user-pasted from Eric's logged-in Amazon session; the unauthenticated Apify/WebFetch path returns truncated or no review text.

## Per-review schema

```json
{
  "reviewer_name": "string",
  "rating": 5,
  "title": "string",
  "review_date": "YYYY-MM-DD",
  "format": "Hardcover" | "Audiobook" | "Kindle",
  "verified_purchase": true | false,
  "helpful_count": 0,
  "has_customer_image": true | false,
  "text": "verbatim review body",
  "shipped_as_entry_id": "content/entries/...json filename without extension, or null"
}
```

## When updating

When a new snapshot arrives, write a new `YYYY-MM-DD.json` file (don't overwrite). The latest snapshot is the source of truth for current state; older snapshots preserve history.

When shipping a review as a timeline entry, update the `shipped_as_entry_id` field on the latest snapshot so future agents don't re-ship it.
