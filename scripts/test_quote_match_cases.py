"""The shared quote-match corpus, from the Python side.

data/quote-match-cases.json is loaded by this module and by
tests/quote-match.test.ts. Two checkers answer "does this quote appear in this
text" — quote_integrity.py offline against a captured source text, and
scripts/quote-match.ts live against the fetched page — in two languages, with
no shared code. Nothing made them agree, so the ` … ` elision convention
reached the Python gate on 2026-10-28 and the TypeScript gate three days later,
during which the live gate reported every one of the 23 entries carrying a
marked cut as a composite.

A convention added to one language now fails the other language's tests until
it is added there too. See
docs/postmortems/2026-10-31-the-elision-convention-one-gate-never-learned.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from quote_integrity import match_quote  # noqa: E402

CASES = json.loads((ROOT / "data" / "quote-match-cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_corpus(case):
    verdict = match_quote(case["quote"], case["text"])
    found = verdict.name in ("EXACT", "NORMALISED")
    assert found is (case["expect"] == "found"), (
        f"{case['name']}: python verdict {verdict.name}, expected {case['expect']}"
    )
