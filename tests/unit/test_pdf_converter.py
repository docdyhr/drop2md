"""Unit tests for the tiered PDF converter selection logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc2md.converters import ConversionError, ConverterResult
from doc2md.converters.pdf import (
    DoclingPdfConverter,
    LegacyPdfConverter,
    MarkerPdfConverter,
    PyMuPdfConverter,
    TieredPdfConverter,
)


def _make_result(converter_name: str = "mock") -> ConverterResult:
    return ConverterResult(markdown="# Hello", converter_used=converter_name)


@pytest.mark.unit
def test_first_available_tier_wins(tmp_path):
    """TieredPdfConverter uses the first available tier."""
    mock_result = _make_result("marker")
    with (
        patch.object(MarkerPdfConverter, "is_available", return_value=True),
        patch.object(MarkerPdfConverter, "convert", return_value=mock_result),
    ):
        path = tmp_path / "test.pdf"
        path.touch()
        result = TieredPdfConverter().convert(path, tmp_path)
    assert result.converter_used == "marker"


@pytest.mark.unit
def test_falls_through_when_unavailable(tmp_path):
    """Unavailable tiers are skipped; next available tier is used."""
    mock_result = _make_result("docling")
    with (
        patch.object(MarkerPdfConverter, "is_available", return_value=False),
        patch.object(DoclingPdfConverter, "is_available", return_value=True),
        patch.object(DoclingPdfConverter, "convert", return_value=mock_result),
    ):
        path = tmp_path / "test.pdf"
        path.touch()
        result = TieredPdfConverter().convert(path, tmp_path)
    assert result.converter_used == "docling"


@pytest.mark.unit
def test_falls_through_on_exception(tmp_path):
    """If a tier raises, the next tier is tried."""
    mock_result = _make_result("pymupdf4llm")
    with (
        patch.object(MarkerPdfConverter, "is_available", return_value=True),
        patch.object(MarkerPdfConverter, "convert", side_effect=RuntimeError("boom")),
        patch.object(DoclingPdfConverter, "is_available", return_value=False),
        patch.object(PyMuPdfConverter, "is_available", return_value=True),
        patch.object(PyMuPdfConverter, "convert", return_value=mock_result),
    ):
        path = tmp_path / "test.pdf"
        path.touch()
        result = TieredPdfConverter().convert(path, tmp_path)
    assert result.converter_used == "pymupdf4llm"


@pytest.mark.unit
def test_all_tiers_exhausted_raises(tmp_path):
    """ConversionError raised when every tier fails or is unavailable."""
    with (
        patch.object(MarkerPdfConverter, "is_available", return_value=False),
        patch.object(DoclingPdfConverter, "is_available", return_value=False),
        patch.object(PyMuPdfConverter, "is_available", return_value=False),
        patch.object(LegacyPdfConverter, "is_available", return_value=False),
    ):
        path = tmp_path / "test.pdf"
        path.touch()
        with pytest.raises(ConversionError):
            TieredPdfConverter().convert(path, tmp_path)


@pytest.mark.unit
def test_legacy_always_available():
    assert LegacyPdfConverter.is_available() is True


@pytest.mark.unit
def test_real_pdf_reaches_legacy(sample_pdf, tmp_path):
    """sample.pdf can be converted via legacy tier (pdfplumber)."""
    with (
        patch.object(MarkerPdfConverter, "is_available", return_value=False),
        patch.object(DoclingPdfConverter, "is_available", return_value=False),
        patch.object(PyMuPdfConverter, "is_available", return_value=False),
    ):
        result = TieredPdfConverter().convert(sample_pdf, tmp_path)
    assert result.markdown
    assert result.converter_used == "pdfplumber"
