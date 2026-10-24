"""Tests for find_ondisk_images — unimaged entries whose photo is already here.

Twice in two days a headshot was hunted on the web while it sat in
public/images/people/ under a name variant: Bob Sutton as robert-sutton.jpg on
2026-10-23, then five more the next morning. The scan prompts were patched to
say "check the disk first", which is an instruction, not a mechanism. This is
the mechanism.

The matching has to be strict. A substring pass over the same data returned 41
"hits", among them "Ann Armbrecht" matched against susanne-h-ann-estad.jpg —
a wrong face is worse than no face, so single tokens never match.
"""

import json

import pytest

from find_ondisk_images import find_matches, slugify


class TestSlugify:
    def test_lowercases_and_hyphenates(self):
        assert slugify("Bob Sutton") == "bob-sutton"

    def test_strips_accents_so_disk_names_match(self):
        assert slugify("Damjana Nurković") == "damjana-nurkovic"
        assert slugify("Sara Muñoz Madrid") == "sara-munoz-madrid"

    def test_drops_punctuation_and_initials_dots(self):
        assert slugify("Mohammed A. AlGhamdi") == "mohammed-a-alghamdi"
        assert slugify("Taylor M.") == "taylor-m"


class TestFindMatches:
    def _entry(self, **kw):
        base = dict(id="2026-01-01-x", attribution="Bob Sutton",
                    image=None, attribution_image=None, type="endorsement")
        base.update(kw)
        return base

    def test_finds_an_entry_whose_headshot_is_already_on_disk(self):
        m = find_matches([self._entry()], {"robert-sutton.jpg", "bob-sutton.jpg"})
        assert len(m) == 1
        assert m[0]["file"] == "bob-sutton.jpg"

    def test_single_token_never_matches(self):
        """'Ann' inside 'hannestad' is the 41-false-positive bug."""
        e = self._entry(attribution="Ann Armbrecht")
        assert find_matches([e], {"susanne-hannestad.jpg"}) == []

    def test_requires_the_whole_name_not_a_prefix(self):
        e = self._entry(attribution="Michael Brown")
        assert find_matches([e], {"michael-brownstein.jpg"}) == []

    def test_skips_entries_that_already_have_an_image(self):
        assert find_matches([self._entry(image="/images/cards/x.png")],
                            {"bob-sutton.jpg"}) == []
        assert find_matches([self._entry(attribution_image="/images/people/y.jpg")],
                            {"bob-sutton.jpg"}) == []

    def test_splits_a_two_person_attribution_and_flags_it(self):
        """Yvonne Bajela & Maria Rotilu: one face for a two-name entry is a
        judgment call, so it is reported but marked ambiguous."""
        e = self._entry(attribution="Yvonne Bajela & Maria Rotilu")
        m = find_matches([e], {"maria-rotilu.jpg"})
        assert len(m) == 1
        assert m[0]["ambiguous"] is True

    def test_single_name_entries_are_not_ambiguous(self):
        m = find_matches([self._entry()], {"bob-sutton.jpg"})
        assert m[0]["ambiguous"] is False

    def test_reports_which_other_entries_vouch_for_the_file(self):
        """A file already used for the same name elsewhere is identity evidence."""
        unimaged = self._entry(id="2026-02-02-new")
        other = self._entry(id="2026-01-01-old", attribution_image="/images/people/bob-sutton.jpg")
        m = find_matches([unimaged, other], {"bob-sutton.jpg"})
        assert m[0]["vouched_by"] == ["2026-01-01-old"]

    def test_unvouched_file_is_reported_with_no_voucher(self):
        m = find_matches([self._entry()], {"bob-sutton.jpg"})
        assert m[0]["vouched_by"] == []

    def test_entry_without_an_attribution_is_skipped(self):
        assert find_matches([self._entry(attribution=None)], {"bob-sutton.jpg"}) == []

    def test_matches_any_image_extension(self):
        m = find_matches([self._entry()], {"bob-sutton.png"})
        assert m[0]["file"] == "bob-sutton.png"


class TestSkips:
    """A match that was deliberately rejected must stop reporting.

    scan-coverage.py learned this the hard way: a fixed gap with no ack
    "reports forever and the report becomes noise nobody reads" (2026-10-17).
    Eric's own entry matches eric-ries.jpg every run, but media entries sourced
    to Eric render no attribution_image at all, so wiring it is a no-op that
    check-images-render then flags. It needs to be recorded, not re-decided.
    """

    def _entry(self, **kw):
        base = dict(id="2026-01-01-x", attribution="Bob Sutton",
                    image=None, attribution_image=None, type="endorsement")
        base.update(kw)
        return base

    def test_a_skipped_entry_is_not_reported(self):
        skips = {"2026-01-01-x": "renders no attribution_image"}
        assert find_matches([self._entry()], {"bob-sutton.jpg"}, skips=skips) == []

    def test_skips_are_keyed_by_entry_id_not_by_file(self):
        """Another entry may legitimately want the same photo."""
        skips = {"2026-01-01-x": "reason"}
        other = self._entry(id="2026-02-02-y")
        m = find_matches([self._entry(), other], {"bob-sutton.jpg"}, skips=skips)
        assert [x["id"] for x in m] == ["2026-02-02-y"]

    def test_no_skips_argument_behaves_as_before(self):
        assert len(find_matches([self._entry()], {"bob-sutton.jpg"})) == 1
