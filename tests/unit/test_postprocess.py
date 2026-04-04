"""Unit tests for GFM postprocessing."""

from __future__ import annotations

import pytest

from drop2md.converters import ConverterResult
from drop2md.postprocess import postprocess
from drop2md.utils.gfm import (
    ensure_trailing_newline,
    fix_table_alignment,
    normalize_headings,
    strip_page_markers,
)


@pytest.mark.unit
def test_strip_page_markers():
    md = "<!-- Page 1 -->\nText\n<!-- Page 2 -->\nMore"
    result = strip_page_markers(md)
    assert "<!-- Page" not in result
    assert "Text" in result


@pytest.mark.unit
def test_normalize_headings_single_h1():
    md = "# Title\n## Section\n### Subsection"
    result = normalize_headings(md)
    assert result.count("\n# ") == 0  # Only first line starts the doc
    assert "# Title" in result


@pytest.mark.unit
def test_normalize_headings_deduplicates_h1():
    md = "# Title One\n\n# Title Two\n\n# Title Three"
    result = normalize_headings(md)
    h1_count = result.count("\n# ") + (1 if result.startswith("# ") else 0)
    assert h1_count == 1, f"Expected 1 H1, got {h1_count}"


@pytest.mark.unit
def test_fix_table_alignment_adds_separator():
    md = "| A | B |\n| 1 | 2 |"
    result = fix_table_alignment(md)
    assert "---" in result


@pytest.mark.unit
def test_fix_table_alignment_preserves_valid_table():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = fix_table_alignment(md)
    assert result == md


@pytest.mark.unit
def test_ensure_trailing_newline():
    assert ensure_trailing_newline("text") == "text\n"
    assert ensure_trailing_newline("text\n") == "text\n"
    assert ensure_trailing_newline("text\n\n") == "text\n"


@pytest.mark.unit
def test_postprocess_adds_frontmatter(tmp_path):
    result = ConverterResult(
        markdown="# Hello\n\nWorld",
        converter_used="test",
        metadata={"pages": 3},
    )
    source = tmp_path / "test.pdf"
    md = postprocess(result, source, add_frontmatter=True)
    assert md.startswith("---\n")
    assert 'source: "test.pdf"' in md
    assert 'converter: "test"' in md
    assert "pages: 3" in md


@pytest.mark.unit
def test_postprocess_no_frontmatter(tmp_path):
    result = ConverterResult(markdown="# Hello", converter_used="test")
    source = tmp_path / "doc.pdf"
    md = postprocess(result, source, add_frontmatter=False)
    assert not md.startswith("---")
    assert "# Hello" in md


@pytest.mark.unit
def test_postprocess_ends_with_newline(tmp_path):
    result = ConverterResult(markdown="content", converter_used="test")
    source = tmp_path / "doc.pdf"
    md = postprocess(result, source, add_frontmatter=False)
    assert md.endswith("\n")
