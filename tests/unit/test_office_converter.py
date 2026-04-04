"""Unit tests for the Office document converter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConversionError
from drop2md.converters.office import (
    MarkItDownConverter,
    OfficeConverter,
    PandocOfficeConverter,
)


@pytest.mark.unit
def test_markitdown_is_available():
    assert MarkItDownConverter.is_available() is True


@pytest.mark.unit
def test_markitdown_converts_docx(sample_docx, tmp_path):
    result = MarkItDownConverter().convert(sample_docx, tmp_path)
    assert result.markdown
    assert result.converter_used == "markitdown"
    # Should contain headings and table content from fixture
    assert "Annual Technical Report" in result.markdown


@pytest.mark.unit
def test_office_converter_uses_markitdown_first(sample_docx, tmp_path):
    mock_result = MagicMock()
    mock_result.text_content = "# Hello"
    with (
        patch.object(MarkItDownConverter, "is_available", return_value=True),
        patch("markitdown.MarkItDown.convert", return_value=mock_result),
    ):
        result = OfficeConverter().convert(sample_docx, tmp_path)
    assert result.converter_used == "markitdown"


@pytest.mark.unit
def test_office_converter_falls_through_to_pandoc(sample_docx, tmp_path):
    """If MarkItDown is unavailable, PandocOfficeConverter is tried."""
    mock_result = MagicMock()
    mock_result.stdout = "# From Pandoc"
    mock_result.returncode = 0
    with (
        patch.object(MarkItDownConverter, "is_available", return_value=False),
        patch.object(PandocOfficeConverter, "is_available", return_value=True),
        patch("subprocess.run", return_value=mock_result),
    ):
        result = OfficeConverter().convert(sample_docx, tmp_path)
    assert result.converter_used == "pandoc"


@pytest.mark.unit
def test_office_converter_raises_when_all_unavailable(tmp_path):
    path = tmp_path / "test.docx"
    path.touch()
    with (
        patch.object(MarkItDownConverter, "is_available", return_value=False),
        patch.object(PandocOfficeConverter, "is_available", return_value=False),
        pytest.raises(ConversionError),
    ):
        OfficeConverter().convert(path, tmp_path)


@pytest.mark.unit
def test_pandoc_rejects_unsupported_format(tmp_path):
    path = tmp_path / "data.xlsx"
    path.touch()
    with (
        patch.object(PandocOfficeConverter, "is_available", return_value=True),
        pytest.raises(ConversionError, match="does not support"),
    ):
        PandocOfficeConverter().convert(path, tmp_path)
