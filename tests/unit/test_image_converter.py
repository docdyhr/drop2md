"""Unit tests for the image OCR converter."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters.image import ImageConverter


@pytest.mark.unit
def test_image_converter_is_available():
    # pytesseract + Pillow are installed via [ocr] extra
    pytest.importorskip("pytesseract")
    assert ImageConverter.is_available() is True


@pytest.mark.unit
def test_image_converter_extracts_ocr_text(sample_png, tmp_path):
    """Real OCR on sample.png should find known text."""
    pytest.importorskip("pytesseract")
    result = ImageConverter().convert(sample_png, tmp_path)
    assert result.converter_used == "image-ocr"
    # sample.png contains "drop2md Image OCR Test" — tesseract should find it
    assert "drop2md" in result.markdown


@pytest.mark.unit
def test_image_converter_includes_image_reference(sample_png, tmp_path):
    """Output markdown must include an image ref to the copied file."""
    result = ImageConverter().convert(sample_png, tmp_path)
    assert "![" in result.markdown
    assert "sample" in result.markdown


@pytest.mark.unit
def test_image_converter_copies_image_to_output(sample_png, tmp_path):
    """The source image is copied into output_dir/images/."""
    ImageConverter().convert(sample_png, tmp_path)
    dest = tmp_path / "images" / sample_png.name
    assert dest.exists()
    assert dest.stat().st_size == sample_png.stat().st_size


@pytest.mark.unit
def test_image_converter_result_lists_image_path(sample_png, tmp_path):
    """result.images contains the path to the copied image."""
    result = ImageConverter().convert(sample_png, tmp_path)
    assert len(result.images) == 1
    assert result.images[0].name == sample_png.name


@pytest.mark.unit
def test_image_converter_ocr_failure_adds_warning(tmp_path):
    """If OCR fails, a warning is added and conversion still succeeds."""
    png = tmp_path / "test.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG magic bytes

    mock_pytess = MagicMock()
    mock_pytess.image_to_string.side_effect = RuntimeError("tesseract crashed")
    mock_pil_image_module = MagicMock()
    mock_pil = MagicMock()
    mock_pil.Image = mock_pil_image_module

    with patch.dict(sys.modules, {"pytesseract": mock_pytess, "PIL": mock_pil, "PIL.Image": mock_pil_image_module}):
        result = ImageConverter().convert(png, tmp_path)

    assert any("OCR failed" in w for w in result.warnings)
    assert "![" in result.markdown  # image ref still present


@pytest.mark.unit
def test_image_converter_no_duplicate_copy(sample_png, tmp_path):
    """Running convert twice does not error — existing image is not overwritten."""
    ImageConverter().convert(sample_png, tmp_path)
    ImageConverter().convert(sample_png, tmp_path)  # second run — must not raise


@pytest.mark.unit
def test_image_converter_unavailable_adds_warning(tmp_path):
    """When pytesseract is not importable, warning is added to result."""
    png = tmp_path / "img.png"
    from PIL import Image
    Image.new("RGB", (10, 10), "white").save(str(png))

    with patch.object(ImageConverter, "is_available", return_value=False):
        result = ImageConverter().convert(png, tmp_path)

    assert any("pytesseract" in w for w in result.warnings)
    assert "*No OCR text extracted.*" in result.markdown
