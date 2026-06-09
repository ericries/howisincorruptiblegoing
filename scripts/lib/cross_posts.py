"""Cross-post state management for the daily Buffer cross-post agent.

See docs/buffer-crosspost-guide.md for the calling contract.
"""
from urllib.parse import urlparse

PLATFORMS = ("linkedin", "x", "bluesky", "instagram")

# host → platform key. www. prefix is stripped before lookup.
_HOST_TO_PLATFORM = {
    "linkedin.com": "linkedin",
    "x.com": "x",
    "twitter.com": "x",
    "bsky.app": "bluesky",
    "instagram.com": "instagram",
}


def _host_to_platform(host: str | None) -> str | None:
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return _HOST_TO_PLATFORM.get(host)


def infer_source_markers(entry: dict) -> dict:
    """Return a dict mapping platform→"source" for any platform whose domain
    appears in entry.source_url or entry.source_urls[].url."""
    urls = []
    if entry.get("source_url"):
        urls.append(entry["source_url"])
    for item in entry.get("source_urls") or []:
        if item and item.get("url"):
            urls.append(item["url"])

    markers: dict = {}
    for url in urls:
        platform = _host_to_platform(urlparse(url).hostname)
        if platform:
            markers[platform] = "source"
    return markers


def merge_state(existing: dict, new: dict) -> dict:
    """Merge `new` into `existing`. Source markers must never overwrite an
    existing scheduled timestamp. Returns the merged dict; does not mutate."""
    out: dict = {entry_id: dict(entry) for entry_id, entry in existing.items()}

    for entry_id, channels in new.items():
        if entry_id not in out:
            out[entry_id] = {}
        for platform, value in channels.items():
            current = out[entry_id].get(platform)
            # Scheduled timestamp wins over a "source" marker
            if current and current != "source" and value == "source":
                continue
            # Otherwise the new value wins (None overwrites None too — harmless)
            out[entry_id][platform] = value

    # Fill missing platforms with None for any entry touched
    for entry_id in out:
        for p in PLATFORMS:
            out[entry_id].setdefault(p, None)

    return out
