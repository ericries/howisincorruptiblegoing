#!/usr/bin/env python3
"""Validate image fields for changed entry files.

For each entry, if the `image` field is non-null, verify:
  - The file exists at content/{image}
  - The file is under 5 MB

Usage:
    python scripts/review_bot/check_images.py content/entries/file1.json ...

Exit 0 if all pass. Exit 1 if any fail.
"""

import json
import os
import sys

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def main() -> int:
    changed_files = sys.argv[1:]

    if not changed_files:
        print("No entry files specified — nothing to check.")
        return 0

    has_failures = False

    for filepath in changed_files:
        if not os.path.isfile(filepath):
            print(f"WARN  File not found: {filepath} — skipping")
            continue

        try:
            with open(filepath, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN  Could not read {filepath}: {exc} — skipping")
            continue

        image = data.get("image")

        if image is None:
            print(f"OK    {filepath}: no image field — skipping")
            continue

        if not isinstance(image, str) or image == "":
            print(f"WARN  {filepath}: image field is not a valid string — skipping")
            continue

        image_path = os.path.join(os.getcwd(), "content", image)

        if not os.path.isfile(image_path):
            has_failures = True
            print(f"FAIL  Image not found: {image_path}")
            print(f"      Referenced in: {filepath}")
            continue

        size = os.path.getsize(image_path)
        if size > MAX_IMAGE_BYTES:
            has_failures = True
            print(f"FAIL  Image too large: {image_path}")
            print(f"      Size: {size:,} bytes (max {MAX_IMAGE_BYTES:,} bytes / 5 MB)")
            print(f"      Referenced in: {filepath}")
        else:
            print(f"OK    {filepath}: image {image_path} exists ({size:,} bytes)")

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
