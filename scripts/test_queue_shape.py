"""The comment-archive queue builder assumes a shape the actor does not emit.

`harvestapi/linkedin-post-search` with scrapeComments represents every comment
TWICE: nested under its post as `post["comments"]`, and again as a flat
top-level sibling carrying `postId`. `queue_from_posts` iterates
`for post in items` and treats every top-level item as a post, so the flat
siblings fall into the post branch and are queued with `parent_post: None`.

Both representations produce the same stable identifier, and the queue dedups
by identifier keeping the first seen. The stream usually BEGINS with a comment
(observed shape `cPcPcccc...`), so the parentless flat record normally wins and
the nested record that carries the correct parent is thrown away.

Measured on 2026-10-30: 34 of 247 candidates had no parent_post, and three of
the nine records archived that day went to disk without one. That defeats the
standing rule to read the parent post in full before judging a comment whose
relevance depends on it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "asc", Path(__file__).resolve().parent / "archive-social-comments.py")
asc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(asc)


def post(pid: str, text: str, comments=None):
    return {
        "id": pid,
        "author": {"name": "Eric Ries", "info": "Author"},
        "content": text,
        "linkedinUrl": f"https://www.linkedin.com/posts/eries_x-activity-{pid}-aa",
        "postedAt": {"date": "2026-10-30T10:00:00.000Z"},
        "engagement": {"likes": 10, "comments": len(comments or [])},
        "comments": comments or [],
    }


def comment(cid: str, pid: str, text: str):
    """A comment as the actor emits it — both nested and flat use this shape."""
    return {
        "id": cid,
        "postId": pid,
        "actor": {"name": "Commenter", "info": "Someone"},
        "commentary": text,
        "linkedinUrl": f"https://www.linkedin.com/feed/update/urn:li:activity:{pid}?commentUrn=urn%3Ali%3Acomment%3A{cid}",
        "createdAt": 1793210750384,
        "engagement": {"likes": 1},
    }


def build(items):
    return asc.queue_from_posts(items, scan_source="linkedin-author-eries", seen=set())


# --- the flat sibling must not be mistaken for a post --------------------------------

def test_flat_comment_sibling_is_classified_as_a_comment():
    c = comment("c1", "p1", "Incorruptible is the real thing.")
    q = build([c, post("p1", "A post about Incorruptible.", [c])])
    kinds = {r["kind"] for r in q}
    assert kinds == {"post", "comment"}, kinds


def test_flat_first_still_yields_a_parent_post():
    """The stream starts with a comment, so the flat record is seen first.

    This is the exact failure: the parentless record wins the dedup and the
    nested one that knows its parent is discarded.
    """
    c = comment("c1", "p1", "Incorruptible is the real thing.")
    q = build([c, post("p1", "A post about Incorruptible.", [c])])
    cmts = [r for r in q if r["kind"] == "comment"]
    assert len(cmts) == 1, "the two representations must collapse to one record"
    assert cmts[0]["parent_post"], "the surviving record must carry its parent"
    assert "A post about Incorruptible" in str(cmts[0]["parent_post"])


def test_nested_first_also_yields_a_parent_post():
    """Order must not decide whether the parent survives."""
    c = comment("c1", "p1", "Incorruptible is the real thing.")
    q = build([post("p1", "A post about Incorruptible.", [c]), c])
    cmts = [r for r in q if r["kind"] == "comment"]
    assert len(cmts) == 1
    assert cmts[0]["parent_post"]


def test_every_comment_record_has_a_parent():
    """The invariant, stated once: a comment without a parent is a bug."""
    cs = [comment(f"c{i}", "p1", f"Incorruptible thought {i}") for i in range(4)]
    q = build([cs[0], cs[1], post("p1", "Post naming Incorruptible.", cs), cs[2], cs[3]])
    for r in q:
        if r["kind"] == "comment":
            assert r["parent_post"], f"{r['identifier']} has no parent_post"


def test_a_flat_comment_whose_post_is_absent_still_records_what_it_knows():
    """A truncated pull can cut a post off while its comments remain.

    The record must still be usable, and must say the parent is unresolved
    rather than silently looking like a comment nobody needed context for.
    """
    c = comment("c9", "p-missing", "Incorruptible changed how I think.")
    q = build([c])
    cmts = [r for r in q if r["kind"] == "comment"]
    assert len(cmts) == 1
    assert cmts[0].get("parent_post_id") == "p-missing"


# --- counts must be measured, not assumed --------------------------------------------

def test_counts_are_derived_from_shape_not_from_list_length():
    """"Scanned 250 posts / 210 comments" was printed for 40 posts.

    The counter took its meaning from the loop variable's name. Counting by
    shape is the difference between a measurement and a restatement of an
    assumption.
    """
    cs = [comment(f"c{i}", "p1", f"Incorruptible {i}") for i in range(3)]
    items = [cs[0], post("p1", "About Incorruptible.", cs), cs[1], cs[2]]
    n_posts, n_comments = asc.count_by_shape(items)
    assert (n_posts, n_comments) == (1, 3)


def test_count_by_shape_handles_a_posts_only_dataset():
    assert asc.count_by_shape([post("p1", "About Incorruptible.")]) == (1, 0)


def test_count_by_shape_handles_an_empty_dataset():
    assert asc.count_by_shape([]) == (0, 0)


# --- the invariant fails loudly rather than silently ---------------------------------

def test_queue_warns_when_a_comment_has_no_resolvable_parent(capsys):
    """A dropped parent must not look like a comment that never had one.

    The failure was invisible for exactly this reason: the preview showed an
    empty field, which reads as "no interesting parent" rather than "the
    parent was thrown away".
    """
    c = comment("c9", "p-missing", "Incorruptible changed how I think.")
    q = asc.queue_from_posts([c], scan_source="linkedin-author-eries",
                             seen=set(), verbose=True)
    err = capsys.readouterr().out + capsys.readouterr().err
    assert q and q[0]["parent_post"] is None
    assert "1 comment" in err and "parent" in err.lower(), err


def test_no_warning_when_every_parent_resolves(capsys):
    c = comment("c1", "p1", "Incorruptible is the real thing.")
    asc.queue_from_posts([c, post("p1", "About Incorruptible.", [c])],
                         scan_source="linkedin-author-eries", seen=set(), verbose=True)
    out = capsys.readouterr().out
    assert "unresolved parent" not in out.lower(), out


# --- regression against the real 2026-10-30 pull -------------------------------------

def test_real_pull_resolves_every_parent():
    """34 of 247 candidates lost their parent on the day this was found."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "data/archive/linkedin-raw/2026-10-30-comments-author.json"
    if not f.exists():
        import pytest
        pytest.skip("raw archive is gitignored/local")
    items = json.loads(f.read_text())
    q = asc.queue_from_posts(items, scan_source="linkedin-author-eries", seen=set())
    orphans = [r for r in q if r["kind"] == "comment" and not r["parent_post"]]
    assert not orphans, f"{len(orphans)} comments still have no parent"


def test_real_pull_counts_posts_correctly():
    """It printed "Scanned 250 posts" for a pull containing 40."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "data/archive/linkedin-raw/2026-10-30-comments-author.json"
    if not f.exists():
        import pytest
        pytest.skip("raw archive is gitignored/local")
    n_posts, n_comments = asc.count_by_shape(json.loads(f.read_text()))
    assert n_posts == 40, n_posts
    assert n_comments == 210, n_comments
