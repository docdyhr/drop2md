"""Unit tests for GFM utility functions."""

import pytest

from drop2md.utils.fs import safe_filename
from drop2md.utils.gfm import (
    ensure_trailing_newline,
    fix_table_alignment,
    normalize_headings,
    strip_page_markers,
)


@pytest.mark.unit
class TestSafeFilename:
    def test_basic(self):
        assert safe_filename("report.pdf") == "report.md"

    def test_spaces_become_underscores(self):
        result = safe_filename("my report 2024.pdf")
        assert " " not in result
        assert result.endswith(".md")

    def test_special_chars_replaced(self):
        result = safe_filename("file (1).pdf")
        assert "(" not in result
        assert ")" not in result

    def test_custom_suffix(self):
        assert safe_filename("doc.pdf", ".txt").endswith(".txt")


@pytest.mark.unit
class TestStripPageMarkers:
    def test_removes_markers(self):
        assert "<!-- Page" not in strip_page_markers("<!-- Page 1 -->\ntext")

    def test_preserves_content(self):
        result = strip_page_markers("<!-- Page 1 -->\nHello World")
        assert "Hello World" in result

    def test_no_markers_unchanged(self):
        text = "Just normal text"
        assert strip_page_markers(text) == text


@pytest.mark.unit
class TestNormalizeHeadings:
    def test_single_h1_unchanged(self):
        md = "# Title\n## Sub"
        assert normalize_headings(md) == md

    def test_duplicate_h1_demoted(self):
        md = "# One\n# Two\n# Three"
        result = normalize_headings(md)
        assert result.startswith("# One")
        assert "## Two" in result
        assert "## Three" in result


@pytest.mark.unit
class TestFixTableAlignment:
    def test_valid_table_unchanged(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        assert fix_table_alignment(table) == table

    def test_missing_separator_added(self):
        table = "| A | B |\n| 1 | 2 |"
        result = fix_table_alignment(table)
        assert "---" in result


@pytest.mark.unit
class TestEnsureTrailingNewline:
    def test_adds_newline(self):
        assert ensure_trailing_newline("text") == "text\n"

    def test_no_double_newline(self):
        assert ensure_trailing_newline("text\n") == "text\n"

    def test_strips_extra_newlines(self):
        assert ensure_trailing_newline("text\n\n\n") == "text\n"
