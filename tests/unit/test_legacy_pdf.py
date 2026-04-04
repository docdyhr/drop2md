"""Unit tests for the legacy pdfplumber-based converter."""

import pytest

from drop2md.converters.legacy_pdf import (
    LegacyPdfConverter,
    _clean_text,
    _is_heading,
    _table_to_markdown,
)


@pytest.mark.unit
def test_clean_text_cid_replacement():
    assert "•" in _clean_text("bullet (cid:7) item")


@pytest.mark.unit
def test_clean_text_collapses_blank_lines():
    result = _clean_text("a\n\n\n\nb")
    assert "\n\n\n" not in result


@pytest.mark.unit
def test_is_heading_all_caps():
    result, level = _is_heading("INTRODUCTION", 12.0)
    assert result is True
    assert level == 2


@pytest.mark.unit
def test_is_heading_long_caps_not_heading():
    long_line = "THIS IS A VERY LONG LINE THAT HAS MORE THAN EIGHT WORDS IN IT"
    result, level = _is_heading(long_line, 12.0)
    assert result is False


@pytest.mark.unit
def test_is_heading_empty_line():
    result, level = _is_heading("", 12.0)
    assert result is False
    assert level == 0


@pytest.mark.unit
def test_table_to_markdown_basic():
    table = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
    md = _table_to_markdown(table)
    assert "| Name | Age |" in md
    assert "| --- | --- |" in md
    assert "| Alice | 30 |" in md


@pytest.mark.unit
def test_table_to_markdown_none_cells():
    table = [["A", None], [None, "B"]]
    md = _table_to_markdown(table)
    assert md  # Should not raise
    assert "|" in md


@pytest.mark.unit
def test_table_to_markdown_empty():
    assert _table_to_markdown([]) == ""
    assert _table_to_markdown([[]]) == ""


@pytest.mark.unit
def test_legacy_converter_is_available():
    # pdfplumber is a core dependency — always available
    assert LegacyPdfConverter.is_available()


@pytest.mark.unit
def test_legacy_converter_real_pdf(sample_pdf, output_dir):
    converter = LegacyPdfConverter()
    result = converter.convert(sample_pdf, output_dir)
    assert result.markdown
    assert result.converter_used == "pdfplumber"
    assert isinstance(result.metadata.get("pages"), int)
