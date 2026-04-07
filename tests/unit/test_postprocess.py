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


# ─── Q-1: Quality scoring ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_quality_high(tmp_path):
    """Rich, structured, warning-free document scores high."""
    from drop2md.postprocess import score_quality
    md = "# Title\n\n## Section\n\n" + ("word " * 450)
    result = ConverterResult(markdown=md, converter_used="marker")
    assert score_quality(md, result) == "high"


@pytest.mark.unit
def test_quality_medium_few_words_with_headings(tmp_path):
    """Moderate word count with at least one heading scores medium."""
    from drop2md.postprocess import score_quality
    md = "# Title\n\n" + ("word " * 150)
    result = ConverterResult(markdown=md, converter_used="marker")
    assert score_quality(md, result) == "medium"


@pytest.mark.unit
def test_quality_low_sparse(tmp_path):
    """Very few words → low quality."""
    from drop2md.postprocess import score_quality
    md = "Just a few words."
    result = ConverterResult(markdown=md, converter_used="pdfplumber")
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_low_scanned_warning(tmp_path):
    """Scanned PDF warning → always low quality regardless of word count."""
    from drop2md.postprocess import score_quality
    md = "# Doc\n\n" + ("word " * 500)
    result = ConverterResult(
        markdown=md,
        converter_used="pdfplumber",
        warnings=["Scanned PDF detected — text extraction may be incomplete."],
    )
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_low_many_warnings(tmp_path):
    """Three or more warnings → always low quality."""
    from drop2md.postprocess import score_quality
    md = "# Doc\n\n## Section\n\n" + ("word " * 500)
    result = ConverterResult(
        markdown=md,
        converter_used="marker",
        warnings=["warn1", "warn2", "warn3"],
    )
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_written_to_frontmatter(tmp_path):
    """postprocess() includes quality: field in YAML frontmatter."""
    md = "# Title\n\n## Section\n\n" + ("word " * 450)
    result = ConverterResult(markdown=md, converter_used="marker")
    source = tmp_path / "doc.pdf"
    out = postprocess(result, source, add_frontmatter=True)
    assert "quality:" in out
    assert "quality: high" in out or "quality: medium" in out or "quality: low" in out


@pytest.mark.unit
def test_quality_not_in_frontmatter_when_disabled(tmp_path):
    """When add_frontmatter=False, quality is not computed or emitted."""
    result = ConverterResult(markdown="# Doc\n\ntext", converter_used="test")
    source = tmp_path / "doc.pdf"
    out = postprocess(result, source, add_frontmatter=False)
    assert "quality:" not in out
