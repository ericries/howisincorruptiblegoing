"""Tests for generate_ig_card.render_ig — IG-format quote card.

Structural assertions only: dimensions, file exists, watermark area has content.
Visual quality (text wrapping, readability, color balance) requires manual review.
"""
from pathlib import Path

import pytest
from PIL import Image

from generate_ig_card import render_ig

IG_W, IG_H = 1080, 1350


def test_render_writes_file(tmp_path):
    out = tmp_path / "x.png"
    entry = {"blockquote": "Q.", "attribution": "A", "attribution_title": "T"}
    render_ig(entry, out)
    assert out.exists()


def test_render_dimensions_1080x1350(tmp_path):
    out = tmp_path / "x.png"
    entry = {"blockquote": "Q.", "attribution": "A", "attribution_title": "T"}
    render_ig(entry, out)
    assert Image.open(out).size == (IG_W, IG_H)


def test_render_short_quote(tmp_path):
    out = tmp_path / "x.png"
    entry = {
        "blockquote": "A book whose time has come.",
        "attribution": "Steen Thomsen",
        "attribution_title": "Professor of Corporate Governance, Copenhagen Business School",
    }
    render_ig(entry, out)
    assert Image.open(out).size == (IG_W, IG_H)


def test_render_long_quote(tmp_path):
    out = tmp_path / "x.png"
    entry = {
        "blockquote": (
            "This book will possibly be more important than the Lean Startup ever "
            "was – for you, your company and society as a whole."
        ),
        "attribution": "Steve Blank",
        "attribution_title": "Customer-development pioneer; Adjunct Professor, Stanford University",
    }
    render_ig(entry, out)
    assert Image.open(out).size == (IG_W, IG_H)


def test_render_handles_missing_optional_fields(tmp_path):
    out = tmp_path / "x.png"
    entry = {"blockquote": "Bare minimum.", "attribution": "Author"}
    render_ig(entry, out)
    assert out.exists()


def test_watermark_area_has_rendered_content(tmp_path):
    """Bottom-edge strip must contain non-background pixels (watermark rendered)."""
    out = tmp_path / "x.png"
    entry = {"blockquote": "Q.", "attribution": "A", "attribution_title": "T"}
    render_ig(entry, out)
    img = Image.open(out).convert("RGB")
    # Bottom 80px × full width — the watermark area
    bottom = img.crop((0, img.height - 80, img.width, img.height))
    bg = (245, 241, 232)
    non_bg = sum(1 for p in bottom.getdata() if p != bg)
    assert non_bg > 100, "watermark area appears empty"
