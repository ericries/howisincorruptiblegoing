"""A LinkedIn URL in an entry must match the one in the raw archive, byte for byte.

Twice in two days I typed a source_urls entry from memory instead of reading it
from the dataset that was already on disk: a tweet id with no digits on
2026-11-03, and on 2026-11-04 a Burka follow-up whose slug AND activity id were
both invented. Both were caught by hand. The activity id is the canonical part
of a LinkedIn post URL, so if it appears in an archive the whole URL is knowable
and a mismatch is a fabrication.
"""
import json
import check_source_urls as csu


def _archive(tmp_path, *urls):
    d = tmp_path / "linkedin-raw"
    d.mkdir(parents=True, exist_ok=True)
    (d / "2026-11-04-keyword.json").write_text(
        json.dumps([{"linkedinUrl": u} for u in urls]))
    return d


REAL = "https://www.linkedin.com/posts/dburka_4-thought-provoking-quotes-from-incorruptible-activity-7523701189675417600-dgwU"
FAKE = "https://www.linkedin.com/posts/dburka_some-of-our-favorite-quotes-from-incorruptible-activity-7523701189675417600-mXnG"


def test_an_invented_slug_on_a_known_activity_id_is_a_failure(tmp_path):
    raw = _archive(tmp_path, REAL)
    assert csu.check_urls([FAKE], raw_dir=raw) == [(FAKE, REAL)]


def test_the_archived_url_passes(tmp_path):
    raw = _archive(tmp_path, REAL)
    assert csu.check_urls([REAL], raw_dir=raw) == []


def test_an_activity_id_in_no_archive_is_not_judged(tmp_path):
    # Legacy entries predate the raw archives; absence is not evidence.
    raw = _archive(tmp_path, REAL)
    other = "https://www.linkedin.com/posts/someone_x-activity-1111111111111111111-aaaa"
    assert csu.check_urls([other], raw_dir=raw) == []


def test_a_non_linkedin_url_is_ignored(tmp_path):
    raw = _archive(tmp_path, REAL)
    assert csu.check_urls(["https://omny.fm/shows/x/y"], raw_dir=raw) == []


def test_a_comment_permalink_does_not_convict_the_canonical_post_url(tmp_path):
    # A comment permalink embeds its PARENT post's activity id. Indexing those
    # made the first run of this checker report 33 failures, every one of them
    # a correct /posts/ URL measured against a /feed/update/ comment link for
    # the same post. When a checker reports a wall, suspect the checker.
    d = tmp_path / "linkedin-raw"
    d.mkdir(parents=True)
    (d / "2026-11-02-comments-author.json").write_text(json.dumps([{
        "linkedinUrl": "https://www.linkedin.com/feed/update/urn:li:activity:7523036246164672512"
                       "?commentUrn=urn%3Ali%3Acomment%3A%28activity%3A7523036246164672512%2C999%29"}]))
    canonical = ("https://www.linkedin.com/posts/robert-pasin_i-recently-read-eric-ries-excellent-new-"
                 "activity-7523036246164672512-eI1F")
    assert csu.check_urls([canonical], raw_dir=d) == []


def test_a_comment_permalink_in_an_entry_is_itself_not_judged(tmp_path):
    d = tmp_path / "linkedin-raw"
    d.mkdir(parents=True)
    (d / "x.json").write_text(json.dumps([{"linkedinUrl": REAL}]))
    perma = ("https://www.linkedin.com/feed/update/urn:li:activity:7523701189675417600"
             "?commentUrn=urn%3Ali%3Acomment%3A%28activity%3A7523701189675417600%2C42%29")
    assert csu.check_urls([perma], raw_dir=d) == []
