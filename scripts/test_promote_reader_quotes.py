"""Tests for the reader-quote promotion script.

Run: uv run --with pytest pytest scripts/test_promote_reader_quotes.py
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "promote", Path(__file__).resolve().parent / "promote-reader-quotes.py"
)
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)


# --- role lines ---------------------------------------------------------

def test_decorative_emoji_stripped_from_titles():
    assert pr.clean_title("Launching Innovation Globally 💡🔥🚀") == "Launching Innovation Globally"
    assert pr.clean_title("Summer sabbatical 😎") == "Summer sabbatical"


def test_plain_titles_untouched():
    for s in ["General Counsel at Outsmart", "Co-Founder, CEO @ Pennant"]:
        assert pr.clean_title(s) == s


def test_trailing_separators_trimmed():
    assert pr.clean_title("Founder ·") == "Founder"
    assert pr.clean_title("CEO —") == "CEO"


# --- avatar slugs -------------------------------------------------------

def test_slug_from_name():
    assert pr.avatar_slug("Sarah L. Brinton") == "sarah-l-brinton"
    assert pr.avatar_slug("Ryan Nowicki Stewart") == "ryan-nowicki-stewart"


def test_slug_handles_punctuation_and_case():
    assert pr.avatar_slug("Carol Van Den Hende") == "carol-van-den-hende"
    assert pr.avatar_slug("Dmytro  Lobod") == "dmytro-lobod"
    assert pr.avatar_slug("O'Brien, Pat") == "o-brien-pat"


def test_slug_never_empty():
    assert pr.avatar_slug("") == "reader"
    assert pr.avatar_slug("🎉") == "reader"


# --- placeholder rejection ---------------------------------------------

def test_linkedin_ghost_avatar_is_rejected():
    """LinkedIn serves a generic static.licdn.com silhouette for users with no
    photo; saving that would put identical grey heads across the band."""
    assert not pr.is_real_avatar("https://static.licdn.com/aero-v1/sc/h/1c5u578iilxfi4m4dvc4q810q")
    assert not pr.is_real_avatar("")
    assert not pr.is_real_avatar(None)


def test_real_media_avatar_is_accepted():
    assert pr.is_real_avatar(
        "https://media.licdn.com/dms/image/v2/D5603AQFLntJ_Uy9-3Q/profile-displayphoto-crop_800_800/x.jpg"
    )
