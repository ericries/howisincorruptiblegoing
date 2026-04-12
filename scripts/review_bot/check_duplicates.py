#!/usr/bin/env python3
"""Check changed entry files for duplicate source_urls against all other entries.

Usage:
    python scripts/review_bot/check_duplicates.py content/entries/file1.json ...

If no args, check all entries against each other.

Exit 0 if no duplicates. Exit 1 if duplicates found.
"""

import json
import os
import sys


def load_entries(entries_dir: str) -> dict[str, dict]:
    """Return {filepath: data} for all JSON files in entries_dir."""
    result = {}
    if not os.path.isdir(entries_dir):
        return result
    for filename in sorted(os.listdir(entries_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(entries_dir, filename)
        try:
            with open(filepath, encoding="utf-8") as fh:
                data = json.load(fh)
            result[filepath] = data
        except (json.JSONDecodeError, OSError):
            # Validation errors handled by validate_entries.py; skip here
            pass
    return result


def main() -> int:
    entries_dir = os.path.join(os.getcwd(), "content", "entries")
    changed_files = sys.argv[1:]

    # Load all entries for comparison
    all_entries = load_entries(entries_dir)

    if not all_entries:
        print("No entry files found — nothing to check.")
        return 0

    # Determine which files to check
    if changed_files:
        check_paths = [os.path.abspath(f) for f in changed_files if os.path.isfile(f)]
    else:
        check_paths = list(all_entries.keys())

    if not check_paths:
        print("No valid entry files to check.")
        return 0

    # Build index: source_url -> list of filepaths
    url_index: dict[str, list[str]] = {}
    for filepath, data in all_entries.items():
        url = data.get("source_url")
        if isinstance(url, str) and url:
            url_index.setdefault(url, []).append(filepath)

    has_duplicates = False

    for check_path in check_paths:
        abs_check = os.path.abspath(check_path)
        data = all_entries.get(abs_check)
        if data is None:
            # Try loading directly (file may not be in entries_dir yet)
            try:
                with open(abs_check, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"WARN  Could not read {check_path}: {exc}")
                continue

        url = data.get("source_url")
        if not isinstance(url, str) or not url:
            continue

        duplicates = [p for p in url_index.get(url, []) if os.path.abspath(p) != abs_check]

        if duplicates:
            has_duplicates = True
            print(f"FAIL  Duplicate source_url in {check_path}")
            print(f"      URL: {url}")
            for dup in duplicates:
                print(f"      Also in: {dup}")
        else:
            print(f"OK    {check_path}: source_url is unique")

    return 1 if has_duplicates else 0


if __name__ == "__main__":
    sys.exit(main())
