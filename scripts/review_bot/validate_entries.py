#!/usr/bin/env python3
"""Schema validation and injection detection for content/entries/ JSON files.

Exit 0 if all entries pass. Exit 1 if any fail.
"""

import json
import os
import re
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Schema rules
# ---------------------------------------------------------------------------

REQUIRED_STRING_FIELDS = [
    "id", "date", "type", "title", "summary", "blockquote",
    "blockquote_source", "source_url", "scanner_source", "created_at",
]

NULLABLE_STRING_FIELDS = ["image", "attribution", "attribution_title", "attribution_image"]

VALID_TYPES = {"event", "endorsement", "review", "social", "podcast", "media", "milestone"}
VALID_SCANNER_SOURCES = {"web-search", "social-scan", "manual", "rss"}

ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SOURCE_URL_RE = re.compile(r"^https?://")

MAX_LENGTHS = {
    "title": 200,
    "summary": 500,
    "blockquote": 1000,
}

# ---------------------------------------------------------------------------
# Injection detection
# ---------------------------------------------------------------------------

# Patterns that signal prompt injection attempts (case-insensitive)
INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore above instructions",
    "disregard previous",
    "you are now a",
    "output your system prompt",
    "output the system prompt",
    "reveal your secret",
    "reveal your hidden",
    "reveal your system",
    "reveal the secret",
    "reveal the hidden",
    "reveal the system",
]

# Prefixes that mimic chat turn markers
ROLE_PREFIX_RE = re.compile(r"^\s*(system|human|user|assistant)\s*:", re.IGNORECASE | re.MULTILINE)

# Dangerous HTML tags
HTML_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed|form|input|link|meta|style)\b",
    re.IGNORECASE,
)

# Zero-width and invisible characters
ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}

# RTL override / bidi control characters
RTL_RANGE = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))

# Base64 payload: 20+ consecutive base64 chars (letters, digits, +, /, =)
BASE64_RE = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

ANOMALOUS_LENGTH = 5000


def _string_values(data: dict) -> list[tuple[str, str]]:
    """Yield (field_name, value) for all string values in a flat dict."""
    results = []
    for key, val in data.items():
        if isinstance(val, str):
            results.append((key, val))
    return results


def detect_injection(data: dict) -> list[str]:
    """Return a list of injection warning strings, empty if clean."""
    reasons = []
    string_fields = _string_values(data)

    for field, value in string_fields:
        lower = value.lower()

        # Length anomaly
        if len(value) > ANOMALOUS_LENGTH:
            reasons.append(f"field '{field}' exceeds {ANOMALOUS_LENGTH} chars ({len(value)})")

        # Phrase patterns
        for phrase in INJECTION_PHRASES:
            if phrase in lower:
                reasons.append(f"field '{field}' contains injection phrase: \"{phrase}\"")

        # Role prefixes
        if ROLE_PREFIX_RE.search(value):
            reasons.append(f"field '{field}' contains role-prefix pattern (system:/user:/etc)")

        # HTML tags
        m = HTML_TAG_RE.search(value)
        if m:
            reasons.append(f"field '{field}' contains dangerous HTML tag: <{m.group(1)}>")

        # Zero-width chars
        for ch in value:
            if ch in ZERO_WIDTH_CHARS:
                reasons.append(f"field '{field}' contains zero-width/invisible character U+{ord(ch):04X}")
                break

        # RTL override
        for ch in value:
            if ord(ch) in RTL_RANGE:
                reasons.append(f"field '{field}' contains RTL override character U+{ord(ch):04X}")
                break

        # Base64 payload
        if BASE64_RE.search(value):
            reasons.append(f"field '{field}' contains potential base64 payload")

    return reasons


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_entry(data: dict, filename: str) -> list[str]:
    """Return list of error strings. Empty list means valid."""
    errors = []

    if not isinstance(data, dict):
        return ["entry must be a JSON object"]

    # Required string fields
    for field in REQUIRED_STRING_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
        elif not isinstance(data[field], str):
            errors.append(f"field '{field}' must be a string")
        elif data[field] == "":
            errors.append(f"field '{field}' must not be empty")

    # Nullable string fields
    for field in NULLABLE_STRING_FIELDS:
        if field not in data:
            errors.append(f"missing field: '{field}' (must be present, may be null)")
        elif data[field] is not None and not isinstance(data[field], str):
            errors.append(f"field '{field}' must be a string or null")

    # tags
    if "tags" not in data:
        errors.append("missing required field: 'tags'")
    elif not isinstance(data["tags"], list):
        errors.append("field 'tags' must be an array")
    elif len(data["tags"]) == 0:
        errors.append("field 'tags' must be a non-empty array")
    else:
        for i, tag in enumerate(data["tags"]):
            if not isinstance(tag, str) or tag == "":
                errors.append(f"field 'tags[{i}]' must be a non-empty string")

    # type_metadata
    if "type_metadata" not in data:
        errors.append("missing required field: 'type_metadata'")
    elif not isinstance(data["type_metadata"], dict):
        errors.append("field 'type_metadata' must be an object")

    # verified
    if "verified" not in data:
        errors.append("missing required field: 'verified'")
    elif not isinstance(data["verified"], bool):
        errors.append("field 'verified' must be a boolean")

    # Format checks (only if fields exist and are strings)
    if isinstance(data.get("id"), str):
        if not ID_RE.match(data["id"]):
            errors.append(f"field 'id' has invalid format (got \"{data['id']}\", expected YYYY-MM-DD-slug)")

    if isinstance(data.get("date"), str):
        if not DATE_RE.match(data["date"]):
            errors.append(f"field 'date' has invalid format (got \"{data['date']}\", expected YYYY-MM-DD)")

    if isinstance(data.get("type"), str):
        if data["type"] not in VALID_TYPES:
            errors.append(f"field 'type' has invalid value \"{data['type']}\" (must be one of: {', '.join(sorted(VALID_TYPES))})")

    if isinstance(data.get("scanner_source"), str):
        if data["scanner_source"] not in VALID_SCANNER_SOURCES:
            errors.append(f"field 'scanner_source' has invalid value \"{data['scanner_source']}\" (must be one of: {', '.join(sorted(VALID_SCANNER_SOURCES))})")

    if isinstance(data.get("source_url"), str):
        if not SOURCE_URL_RE.match(data["source_url"]):
            errors.append(f"field 'source_url' must start with http:// or https://")

    if isinstance(data.get("created_at"), str):
        if not CREATED_AT_RE.match(data["created_at"]):
            errors.append(f"field 'created_at' has invalid format (got \"{data['created_at']}\", expected ISO 8601 with Z suffix)")

    # Max length checks
    for field, max_len in MAX_LENGTHS.items():
        if isinstance(data.get(field), str) and len(data[field]) > max_len:
            errors.append(f"field '{field}' exceeds max length {max_len} (got {len(data[field])})")

    # Filename must match id
    if isinstance(data.get("id"), str):
        expected_filename = f"{data['id']}.json"
        if filename != expected_filename:
            errors.append(f"filename \"{filename}\" does not match id \"{data['id']}\" (expected \"{expected_filename}\")")

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    entries_dir = os.path.join(os.getcwd(), "content", "entries")

    if not os.path.isdir(entries_dir):
        print("No content/entries/ directory found — nothing to validate.")
        return 0

    files = sorted(f for f in os.listdir(entries_dir) if f.endswith(".json"))

    if not files:
        print("No entry files found — nothing to validate.")
        return 0

    has_errors = False

    for filename in files:
        filepath = os.path.join(entries_dir, filename)

        # Parse JSON
        try:
            with open(filepath, encoding="utf-8") as fh:
                raw = fh.read()
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"FAIL {filename}:")
            print(f"   - JSON parse error: {exc}")
            has_errors = True
            continue
        except OSError as exc:
            print(f"FAIL {filename}:")
            print(f"   - Could not read file: {exc}")
            has_errors = True
            continue

        errors = validate_entry(data, filename)

        # Injection detection
        if isinstance(data, dict):
            injection_reasons = detect_injection(data)
            for reason in injection_reasons:
                errors.append(f"injection detected: {reason}")

        if errors:
            has_errors = True
            print(f"FAIL {filename}:")
            for err in errors:
                print(f"   - {err}")
        else:
            print(f"OK   {filename}")

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
