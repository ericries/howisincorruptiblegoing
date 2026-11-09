"""Entry summaries drifted from 22 words to 102 and nobody decided to.

CLAUDE.md has said "concise, 1-2 sentences" since the site was built. Median
summary length by month, measured 2026-11-01:

    2026-01  20 words    2026-08  57 words
    2026-04  26 words    2026-10  65 words
    2026-05  38 words    2026-11  102 words

No single summary was unreasonable next to the one before it. The rule was
prose in a file nothing read, so there was no reference point to drift from.
Eric caught it by reading one — "careful about AI-ese, this reads like LLM
speak" — which is the expensive way to find a thing a regex finds for free.

These rules split on how objective they are. A hard FAIL is something a
machine can be sure about: length, a buzzword, the summary quoting the
blockquote back. A WARN is a device that is fine once and a tell when it
saturates — tricolons and em dashes are good writing in moderation, so the
checker reports them and leaves the judgement to a person.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import summary_tics as st  # noqa: E402


def ids(findings):
    return {f.rule for f in findings}


def fails(summary, **kw):
    return {f.rule for f in st.check(summary, **kw) if f.severity == "fail"}


def warns(summary, **kw):
    return {f.rule for f in st.check(summary, **kw) if f.severity == "warn"}


# ── length ───────────────────────────────────────────────────────────────
def test_a_two_sentence_summary_under_the_cap_is_clean():
    """Originally written with "on air last Thursday", which the relative-time
    rule later caught. The source says "el jueves pasado", which can mean this
    past Thursday or the one before; unresolvable, so it is cut rather than
    guessed. The entry's own date already carries the when."""
    s = ("Balayan runs Maure Inmobiliaria in Buenos Aires and has a standing books "
         "slot on Neura, where she recommended Incorruptible on air. "
         "Her written summary tracks the book closely.")
    assert st.check(s) == []


def test_more_than_two_sentences_no_longer_fails():
    """Eric, 2026-11-01: "1-2 sentences is not a hard rule. we want to make them
    as good as is appropriate, with the more important milestones getting more
    attention." Length became a tiered warning; only absurd bloat still fails."""
    assert "length" not in fails("One thing. Two things. Three things. Four.")


def test_over_the_tier_target_warns():
    assert "length" in warns("word " * 80, tier="brief")


def test_a_major_entry_may_run_long_without_a_warning():
    """A Courtois-scale endorsement earns its detail."""
    assert "length" not in warns("word " * 100, tier="major")


def test_the_same_length_warns_for_a_passing_reaction():
    assert "length" in warns("word " * 100, tier="brief")


def test_absurd_bloat_still_fails_at_every_tier():
    assert "length" in fails("word " * 200, tier="major")


def test_tier_is_derived_from_the_entry(tmp_path):
    import json
    major = tmp_path / "m.json"
    major.write_text(json.dumps(
        {"type": "endorsement", "summary": "word " * 100,
         "type_metadata": {"highlight": "X: 'y'"}}))
    assert "length" not in {f.rule for f in st.check_entry(major)}
    plain = tmp_path / "p.json"
    plain.write_text(json.dumps({"type": "reaction", "summary": "word " * 100}))
    assert "length" in {f.rule for f in st.check_entry(plain)}


def test_the_cap_counts_sentences_not_full_stops_inside_abbreviations():
    """'Co-founder of X Inc. and author' is one sentence, not two."""
    s = "She is a partner at Foo Inc. and recommended the book on air last Thursday."
    assert "length" not in fails(s)


# ── corrective antithesis: the single most recognisable LLM tell ─────────
def test_not_x_but_y_fails():
    assert "antithesis" in fails("It is not a book about greed, but a book about structure.")


def test_the_appositive_form_fails():
    """The form Eric flagged: '… is Eric's own argument, not her coinage.'"""
    assert "antithesis" in fails("The line is Eric's own argument, not her coinage.")


def test_isnt_x_its_y_fails():
    assert "antithesis" in fails("This isn't a procedural note — it's the whole argument.")


def test_a_plain_negation_is_not_an_antithesis():
    """Don't flag ordinary negation; only the corrective X/Y pair."""
    assert "antithesis" not in fails("She does not name the publisher anywhere in the post.")


def test_rather_than_inside_a_factual_contrast_is_allowed():
    """The book really does locate the problem in one place over another."""
    s = "She puts the problem in governance and legal structure rather than greed."
    assert "antithesis" not in fails(s)


# ── repo-specific: the summary must not quote the blockquote back ────────
def test_restating_the_blockquote_fails():
    bq = "La idea mas potente del libro es que la confianza es el activo mas subestimado."
    s = "Her own verdict is that la confianza es el activo mas subestimado de los negocios."
    assert "echoes-blockquote" in fails(s, blockquote=bq)


def test_a_few_shared_words_with_the_blockquote_is_fine():
    bq = "Trust is the most underrated asset in business and nobody prices it."
    s = "She recommended the book on air last Thursday and wrote up the argument."
    assert "echoes-blockquote" not in fails(s, blockquote=bq)


# ── vocabulary ───────────────────────────────────────────────────────────
def test_buzzwords_fail():
    assert "buzzword" in fails("The post is a testament to the robust landscape of governance.")


def test_a_buzzword_inside_a_quoted_span_is_not_the_writer_s_word():
    """Someone else may well have said 'testament'. Don't punish reporting it."""
    s = 'She called the book "a testament to patient capital" on air.'
    assert "buzzword" not in fails(s)


# ── saturation warnings, not failures ────────────────────────────────────
def test_more_than_one_em_dash_aside_warns():
    """Written with the naive rule (2 dashes = warn), whose example turned out
    to be a correctly-used matched pair. The rule is asides, not dashes."""
    s = "She runs the firm — a small one. He reviewed it last Thursday — on air."
    assert "em-dash" in warns(s)


def test_a_single_em_dash_is_fine():
    assert "em-dash" not in warns("She reviewed it last Thursday — on air, in Spanish.")


def test_a_tricolon_warns_without_failing():
    s = ("Her summary tracks the book: financial gravity growing with investors, "
         "governance as what fixes it, and Costco and Patagonia as the examples.")
    assert "tricolon" in warns(s)
    assert fails(s) == set()


def test_narrated_candor_warns():
    """'the honest answer', 'I would rather flag this' — moral framing of my own process."""
    assert "narrated-candor" in warns("That is the honest answer, and worth saying plainly.")


# ── reporting ────────────────────────────────────────────────────────────
def test_findings_name_the_offending_span_so_it_can_be_fixed():
    f = [x for x in st.check("It is not a book about greed, but about structure.")][0]
    assert f.span and f.span in "It is not a book about greed, but about structure."


def test_check_entry_reads_summary_and_blockquote_from_the_file(tmp_path):
    import json
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"summary": "word " * 80, "blockquote": "x"}))
    assert "length" in {f.rule for f in st.check_entry(p)}


def test_an_apostrophe_is_not_a_quote_mark():
    """Treating ' as a quote delimiter stripped "isn't a note — it's the
    argument" down to "isn s the argument" and silently disabled every other
    rule on any summary containing two apostrophes."""
    s = "This isn't Eric's framing — it's the reviewer's own."
    assert st._strip_quoted(s).count("isn't") == 1
    assert "antithesis" in fails(s)


# ── scoping: block new drift, don't wall off 404 legacy summaries ────────
def test_an_unchanged_summary_is_skipped(monkeypatch, tmp_path):
    """Editing an entry's image must not be blocked by a summary written in May."""
    import json
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"summary": "word " * 80}))
    monkeypatch.setattr(st, "_head_summary", lambda path: "word " * 80)
    assert st.check_file_vs_head(p) is None


def test_a_rewritten_summary_is_checked(monkeypatch, tmp_path):
    import json
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"summary": "word " * 80}))
    monkeypatch.setattr(st, "_head_summary", lambda path: "a short old summary.")
    assert "length" in {f.rule for f in st.check_file_vs_head(p)}


def test_a_brand_new_entry_is_checked(monkeypatch, tmp_path):
    """No HEAD version at all — new work meets the bar."""
    import json
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"summary": "word " * 80}))
    monkeypatch.setattr(st, "_head_summary", lambda path: None)
    assert "length" in {f.rule for f in st.check_file_vs_head(p)}


def test_a_matched_em_dash_pair_is_one_aside_not_two():
    """"Cantrill — Oxide's co-founder and CTO — spent six minutes" is one
    parenthetical, which is the device's correct use. Counting raw dashes
    flagged good writing, and a checker with false positives gets ignored."""
    s = ("Oxide and Friends runs an annual books episode, and Cantrill — Oxide's "
         "co-founder and CTO — spent six minutes on the book.")
    assert "em-dash" not in warns(s)


def test_two_separate_asides_still_warn():
    s = ("She runs the firm — a small one. He reviewed the book last Thursday — "
         "on air, in Spanish.")
    assert "em-dash" in warns(s)


def test_three_dashes_in_one_sentence_warn():
    s = "She runs the firm — a small one — and reviewed it — on air — last Thursday."
    assert "em-dash" in warns(s)


# ── tense: an entry is a dated record, so it must not drift ──────────────
def test_a_relative_time_word_fails():
    """'upcoming' froze into six entries whose events happened months ago."""
    assert "relative-time" in fails("He flags Eric's upcoming NACD mainstage session.")


def test_next_week_fails():
    assert "relative-time" in fails("She announces Eric is joining the podcast next week.")


def test_last_thursday_fails():
    """My own rewrite, one hour old: 'she recommended it on air last Thursday'."""
    assert "relative-time" in fails("She recommended Incorruptible on air last Thursday.")


def test_an_absolute_date_is_fine():
    assert "relative-time" not in fails("The summit takes place in Amsterdam on 19 November.")


def test_last_as_an_ordinary_adjective_is_not_a_time_word():
    assert "relative-time" not in fails("He returns to it in the last chapter of the book.")


def test_a_relative_time_word_inside_a_quote_is_the_speaker_s():
    s = 'He wrote that he would "finish it next week" and posted a photo.'
    assert "relative-time" not in fails(s)


def test_will_reporting_a_claim_is_not_a_relative_time_word():
    """'the book will change how founders think' is a reported claim, not a date."""
    assert "relative-time" not in fails("He says the book will change how founders think.")


def test_tomorrows_company_is_a_proper_noun_not_a_relative_time():
    """On 2026-11-09 the Drucker Forum summary was failed for the word
    "Tomorrow" — in "Tomorrow's Company", the organisation Mark Goyder founded
    in 1996. A gate that cannot tell a company name from a relative-time word
    pushes the writer to mangle a proper noun to satisfy it, which is the gate
    making the entry worse. Possessive-capitalised use is a name.
    """
    s = ("Goyder founded Tomorrow's Company in 1996 after Charles Handy sent him "
         "to the RSA, then turned to the book for how governance holds a mission.")
    assert [f for f in st.check(s) if f.rule == "relative-time"] == []


def test_a_real_relative_time_word_still_fails():
    s = "He recently read the book and will speak about it tomorrow."
    assert [f for f in st.check(s) if f.rule == "relative-time"]
