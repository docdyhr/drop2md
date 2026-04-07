"""Unit tests for the tiered PDF converter selection logic."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConversionError, ConverterResult
from drop2md.converters.pdf import (
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


# ─── is_available() with mocked imports ──────────────────────────────────────

@pytest.mark.unit
def test_marker_is_available_when_installed():
    """MarkerPdfConverter.is_available() returns True when marker is importable."""
    with patch.dict(sys.modules, {"marker": MagicMock()}):
        assert MarkerPdfConverter.is_available() is True


@pytest.mark.unit
def test_docling_is_available_when_installed():
    """DoclingPdfConverter.is_available() returns True when docling is importable."""
    with patch.dict(sys.modules, {"docling": MagicMock()}):
        assert DoclingPdfConverter.is_available() is True


@pytest.mark.unit
def test_pymupdf_is_available_when_installed():
    """PyMuPdfConverter.is_available() returns True when pymupdf4llm is importable."""
    with patch.dict(sys.modules, {"pymupdf4llm": MagicMock()}):
        assert PyMuPdfConverter.is_available() is True


# ─── convert() via mocked lazy imports ───────────────────────────────────────

@pytest.mark.unit
def test_pymupdf_converter_convert(tmp_path):
    """PyMuPdfConverter.convert() returns markdown from pymupdf4llm.to_markdown()."""
    path = tmp_path / "test.pdf"
    path.write_bytes(b"fake pdf")

    mock_lib = MagicMock()
    mock_lib.to_markdown.return_value = "# From PyMuPDF"

    with patch.dict(sys.modules, {"pymupdf4llm": mock_lib}):
        result = PyMuPdfConverter().convert(path, tmp_path)

    assert result.markdown == "# From PyMuPDF"
    assert result.converter_used == "pymupdf4llm"
    mock_lib.to_markdown.assert_called_once_with(str(path))


@pytest.mark.unit
def test_docling_converter_convert(tmp_path):
    """DoclingPdfConverter.convert() returns markdown and page count."""
    path = tmp_path / "test.pdf"
    path.write_bytes(b"fake pdf")

    mock_doc_result = MagicMock()
    mock_doc_result.document.export_to_markdown.return_value = "# From Docling"
    mock_doc_result.document.num_pages.return_value = 5

    mock_converter_instance = MagicMock()
    mock_converter_instance.convert.return_value = mock_doc_result

    mock_docling_mod = MagicMock()
    mock_docling_mod.DocumentConverter.return_value = mock_converter_instance

    with patch.dict(sys.modules, {
        "docling": MagicMock(),
        "docling.document_converter": mock_docling_mod,
    }):
        result = DoclingPdfConverter().convert(path, tmp_path)

    assert result.markdown == "# From Docling"
    assert result.metadata == {"pages": 5}
    assert result.converter_used == "docling"


@pytest.mark.unit
def test_marker_converter_convert_no_images(tmp_path):
    """MarkerPdfConverter.convert() with no images returns plain markdown."""
    path = tmp_path / "test.pdf"
    path.write_bytes(b"fake pdf")

    mock_pdf_mod = MagicMock()
    mock_models_mod = MagicMock()
    mock_models_mod.create_model_dict.return_value = {}
    mock_output_mod = MagicMock()
    mock_output_mod.text_from_rendered.return_value = ("# From Marker", None, {})

    with patch.dict(sys.modules, {
        "marker": MagicMock(),
        "marker.converters": MagicMock(),
        "marker.converters.pdf": mock_pdf_mod,
        "marker.models": mock_models_mod,
        "marker.output": mock_output_mod,
    }):
        result = MarkerPdfConverter().convert(path, tmp_path)

    assert result.markdown == "# From Marker"
    assert result.converter_used == "marker"
    assert result.images == []


@pytest.mark.unit
def test_marker_converter_saves_pil_images(tmp_path):
    """MarkerPdfConverter saves PIL Image objects (not bytes) via .save()."""

    path = tmp_path / "test.pdf"
    path.write_bytes(b"fake pdf")

    mock_pil_img = MagicMock()  # simulates a PIL Image

    mock_pdf_mod = MagicMock()
    mock_models_mod = MagicMock()
    mock_models_mod.create_model_dict.return_value = {}
    mock_output_mod = MagicMock()
    mock_output_mod.text_from_rendered.return_value = (
        "# With Image", None, {"figure.png": mock_pil_img}
    )

    with patch.dict(sys.modules, {
        "marker": MagicMock(),
        "marker.converters": MagicMock(),
        "marker.converters.pdf": mock_pdf_mod,
        "marker.models": mock_models_mod,
        "marker.output": mock_output_mod,
    }):
        result = MarkerPdfConverter().convert(path, tmp_path)

    mock_pil_img.save.assert_called_once()
    assert len(result.images) == 1


@pytest.mark.unit
def test_marker_converter_saves_bytes_images(tmp_path):
    """MarkerPdfConverter writes raw bytes images directly."""
    path = tmp_path / "test.pdf"
    path.write_bytes(b"fake pdf")

    mock_pdf_mod = MagicMock()
    mock_models_mod = MagicMock()
    mock_models_mod.create_model_dict.return_value = {}
    mock_output_mod = MagicMock()
    mock_output_mod.text_from_rendered.return_value = (
        "# With Bytes Image", None, {"chart.png": b"\x89PNG\r\n\x1a\n"}
    )

    with patch.dict(sys.modules, {
        "marker": MagicMock(),
        "marker.converters": MagicMock(),
        "marker.converters.pdf": mock_pdf_mod,
        "marker.models": mock_models_mod,
        "marker.output": mock_output_mod,
    }):
        MarkerPdfConverter().convert(path, tmp_path)

    saved = tmp_path / "images" / "test_chart.png"
    assert saved.exists()
    assert saved.read_bytes() == b"\x89PNG\r\n\x1a\n"


# ─── Q-2: Scanned PDF detection ──────────────────────────────────────────────

@pytest.mark.unit
def test_scanned_pdf_skips_ml_tiers(tmp_path):
    """Scanned PDFs skip Marker and Docling; pdfplumber is used instead."""
    from drop2md.converters.pdf import _is_scanned_pdf

    path = tmp_path / "scanned.pdf"
    path.touch()

    mock_result = _make_result("pdfplumber")

    with (
        patch("drop2md.converters.pdf._is_scanned_pdf", return_value=True),
        patch.object(MarkerPdfConverter, "is_available", return_value=True),
        patch.object(MarkerPdfConverter, "convert") as mock_marker,
        patch.object(DoclingPdfConverter, "is_available", return_value=True),
        patch.object(DoclingPdfConverter, "convert") as mock_docling,
        patch.object(PyMuPdfConverter, "is_available", return_value=False),
        patch.object(LegacyPdfConverter, "is_available", return_value=True),
        patch.object(LegacyPdfConverter, "convert", return_value=mock_result),
    ):
        result = TieredPdfConverter().convert(path, tmp_path)

    mock_marker.assert_not_called()
    mock_docling.assert_not_called()
    assert result.converter_used == "pdfplumber"
    assert any("Scanned PDF" in w for w in result.warnings)


@pytest.mark.unit
def test_scanned_pdf_warning_in_result(tmp_path):
    """Result carries a scanned-PDF warning when detected."""
    path = tmp_path / "scan.pdf"
    path.touch()

    mock_result = _make_result("pymupdf4llm")

    with (
        patch("drop2md.converters.pdf._is_scanned_pdf", return_value=True),
        patch.object(MarkerPdfConverter, "is_available", return_value=False),
        patch.object(DoclingPdfConverter, "is_available", return_value=False),
        patch.object(PyMuPdfConverter, "is_available", return_value=True),
        patch.object(PyMuPdfConverter, "convert", return_value=mock_result),
    ):
        result = TieredPdfConverter().convert(path, tmp_path)

    assert result.warnings
    assert any("Scanned PDF" in w for w in result.warnings)


@pytest.mark.unit
def test_non_scanned_pdf_uses_normal_tiers(tmp_path):
    """Non-scanned PDFs run through the normal tier order."""
    path = tmp_path / "text.pdf"
    path.touch()

    mock_result = _make_result("marker")

    with (
        patch("drop2md.converters.pdf._is_scanned_pdf", return_value=False),
        patch.object(MarkerPdfConverter, "is_available", return_value=True),
        patch.object(MarkerPdfConverter, "convert", return_value=mock_result),
    ):
        result = TieredPdfConverter().convert(path, tmp_path)

    assert result.converter_used == "marker"
    assert not result.warnings


@pytest.mark.unit
def test_is_scanned_pdf_low_char_count(tmp_path):
    """_is_scanned_pdf returns True when pages have very few characters."""
    from drop2md.converters.pdf import _is_scanned_pdf

    path = tmp_path / "scan.pdf"
    path.touch()

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "ab"  # 2 chars — below threshold of 20

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page, mock_page, mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        assert _is_scanned_pdf(path) is True


@pytest.mark.unit
def test_is_scanned_pdf_sufficient_text(tmp_path):
    """_is_scanned_pdf returns False when pages have sufficient text."""
    from drop2md.converters.pdf import _is_scanned_pdf

    path = tmp_path / "text.pdf"
    path.touch()

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "A" * 100  # 100 chars — above threshold

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        assert _is_scanned_pdf(path) is False


@pytest.mark.unit
def test_is_scanned_pdf_graceful_on_error(tmp_path):
    """_is_scanned_pdf returns False (safe default) if pdfplumber raises."""
    from drop2md.converters.pdf import _is_scanned_pdf

    path = tmp_path / "broken.pdf"
    path.touch()

    with patch("pdfplumber.open", side_effect=Exception("corrupt")):
        assert _is_scanned_pdf(path) is False
