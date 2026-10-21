"""Tests for the orphaned-image check.

On 2026-10-20 it emerged that 58 type=reaction entries carried a sourced
headshot in attribution_image that appeared nowhere in the built site — the
reaction list rendered author, title, quote and link, and dropped the image. Every
morning scan that had dutifully sourced a face for a reaction was doing work
nobody could see, for weeks.

Entry JSON said the image was there. `lint` said the file existed on disk. Both
were true and both were beside the point: nothing checked that the path reached
the HTML. This does, against the real build output, which is the only place the
question can actually be answered.
"""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_images_render", Path(__file__).resolve().parent / "check-images-render.py")
cir = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cir)


def test_an_image_present_in_the_html_is_not_orphaned():
    orphans = cir.find_orphans(
        entries=[{"id": "e1", "type": "reaction", "attribution_image": "/images/people/a.jpg"}],
        html='<img src="/images/people/a.jpg">')
    assert orphans == []


def test_an_image_absent_from_the_html_is_orphaned():
    orphans = cir.find_orphans(
        entries=[{"id": "e1", "type": "reaction", "attribution_image": "/images/people/a.jpg"}],
        html="<p>no images here</p>")
    assert len(orphans) == 1
    assert orphans[0]["entry"] == "e1"
    assert orphans[0]["path"] == "/images/people/a.jpg"
    assert orphans[0]["field"] == "attribution_image"


def test_both_image_fields_are_checked():
    orphans = cir.find_orphans(
        entries=[{"id": "e1", "type": "review",
                  "image": "/images/cards/c.png",
                  "attribution_image": "/images/people/a.jpg"}],
        html="")
    assert {o["field"] for o in orphans} == {"image", "attribution_image"}


def test_null_and_missing_fields_are_skipped():
    assert cir.find_orphans(
        entries=[{"id": "e1", "type": "review", "image": None}], html="") == []


def test_a_whole_field_missing_from_the_build_is_reported_once_not_per_entry():
    # The real signature of the 2026-10-20 bug: every reaction's avatar missing
    # at once, because the component never rendered the field. 58 identical
    # lines would bury the finding.
    entries = [{"id": f"r{i}", "type": "reaction",
                "attribution_image": f"/images/people/p{i}.jpg"} for i in range(58)]
    orphans = cir.find_orphans(entries=entries, html="")
    summary = cir.summarise(orphans)
    assert "58" in summary
    assert "attribution_image" in summary
    assert "reaction" in summary


def test_query_string_and_fragment_do_not_defeat_the_match():
    assert cir.find_orphans(
        entries=[{"id": "e1", "type": "review", "image": "/images/cards/c.png"}],
        html='<img src="/images/cards/c.png?v=2">') == []
