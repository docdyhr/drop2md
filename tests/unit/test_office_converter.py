"""Unit tests for the Office document converter."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConversionError
from drop2md.converters.office import (
    MarkItDownConverter,
    OfficeConverter,
    PandocOfficeConverter,
    _extract_docx_images,
    _extract_office_images,
    _extract_pptx_images,
)


@pytest.mark.unit
def test_markitdown_is_available():
    pytest.importorskip("markitdown")
    assert MarkItDownConverter.is_available() is True


@pytest.mark.unit
def test_markitdown_converts_docx(sample_docx, tmp_path):
    pytest.importorskip("markitdown")
    result = MarkItDownConverter().convert(sample_docx, tmp_path)
    assert result.markdown
    assert result.converter_used == "markitdown"
    # Should contain headings and table content from fixture
    assert "Annual Technical Report" in result.markdown


@pytest.mark.unit
def test_office_converter_uses_markitdown_first(sample_docx, tmp_path):
    mock_result = MagicMock()
    mock_result.text_content = "# Hello"
    mock_markitdown_instance = MagicMock()
    mock_markitdown_instance.convert.return_value = mock_result
    mock_markitdown_module = MagicMock()
    mock_markitdown_module.MarkItDown.return_value = mock_markitdown_instance
    with (
        patch.dict(sys.modules, {"markitdown": mock_markitdown_module}),
        patch.object(MarkItDownConverter, "is_available", return_value=True),
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


@pytest.mark.unit
def test_pandoc_office_is_available():
    mock_run = MagicMock()
    mock_run.returncode = 0
    with patch("subprocess.run", return_value=mock_run):
        assert PandocOfficeConverter.is_available() is True


@pytest.mark.unit
def test_pandoc_office_convert_fails(tmp_path):
    """PandocOfficeConverter raises ConversionError when pandoc returns non-zero."""
    path = tmp_path / "doc.docx"
    path.touch()
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "pandoc: error"
    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(ConversionError, match="pandoc failed"),
    ):
        PandocOfficeConverter().convert(path, tmp_path)


@pytest.mark.unit
def test_markitdown_is_available_true():
    """MarkItDownConverter.is_available returns True when markitdown is importable."""
    mock_mod = MagicMock()
    with patch.dict(sys.modules, {"markitdown": mock_mod}):
        result = MarkItDownConverter.is_available()
    assert result is True


@pytest.mark.unit
def test_office_converter_all_raise_conversion_error(tmp_path):
    """OfficeConverter raises ConversionError when all converters raise exceptions."""
    path = tmp_path / "broken.docx"
    path.touch()
    with (
        patch.object(MarkItDownConverter, "is_available", return_value=True),
        patch.object(MarkItDownConverter, "convert", side_effect=Exception("fail")),
        patch.object(PandocOfficeConverter, "is_available", return_value=True),
        patch.object(
            PandocOfficeConverter, "convert", side_effect=Exception("also fail")
        ),
        pytest.raises(ConversionError),
    ):
        OfficeConverter().convert(path, tmp_path)


# ── Image extraction ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_docx_images_no_package(tmp_path):
    """_extract_docx_images returns [] when python-docx is not installed."""
    path = tmp_path / "test.docx"
    path.touch()
    with patch.dict(sys.modules, {"docx": None}):
        result = _extract_docx_images(path, tmp_path)
    assert result == []


@pytest.mark.unit
def test_extract_docx_images_success(tmp_path):
    """_extract_docx_images extracts and saves image blobs from a DOCX."""
    path = tmp_path / "test.docx"
    path.touch()

    mock_img_part = MagicMock()
    mock_img_part.partname = "/word/media/image1.png"
    mock_img_part.blob = b"\x89PNG\r\n"

    mock_rel = MagicMock()
    mock_rel.reltype = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    )
    mock_rel.target_part = mock_img_part

    mock_doc = MagicMock()
    mock_doc.part.rels = {"rId1": mock_rel}

    mock_docx_module = MagicMock()
    mock_docx_module.Document.return_value = mock_doc

    with patch.dict(sys.modules, {"docx": mock_docx_module}):
        result = _extract_docx_images(path, tmp_path)

    assert len(result) == 1
    assert result[0].suffix == ".png"
    assert result[0].read_bytes() == b"\x89PNG\r\n"


@pytest.mark.unit
def test_extract_pptx_images_no_package(tmp_path):
    """_extract_pptx_images returns [] when python-pptx is not installed."""
    path = tmp_path / "test.pptx"
    path.touch()
    with patch.dict(sys.modules, {"pptx": None, "pptx.util": None}):
        result = _extract_pptx_images(path, tmp_path)
    assert result == []


@pytest.mark.unit
def test_extract_pptx_images_success(tmp_path):
    """_extract_pptx_images extracts images from PPTX slides."""
    path = tmp_path / "test.pptx"
    path.touch()

    mock_image = MagicMock()
    mock_image.blob = b"FAKEPNG"
    mock_image.ext = "png"

    mock_shape = MagicMock()
    mock_shape.shape_type = 13  # MSO_SHAPE_TYPE.PICTURE
    mock_shape.image = mock_image

    mock_slide = MagicMock()
    mock_slide.shapes = [mock_shape]

    mock_prs = MagicMock()
    mock_prs.slides = [mock_slide]

    mock_pptx_module = MagicMock()
    mock_pptx_module.Presentation.return_value = mock_prs
    mock_pptx_util = MagicMock()

    with patch.dict(
        sys.modules, {"pptx": mock_pptx_module, "pptx.util": mock_pptx_util}
    ):
        result = _extract_pptx_images(path, tmp_path)

    assert len(result) == 1
    assert result[0].read_bytes() == b"FAKEPNG"


@pytest.mark.unit
def test_extract_office_images_other_format(tmp_path):
    """_extract_office_images returns [] for formats with no image extraction."""
    path = tmp_path / "data.xlsx"
    result = _extract_office_images(path, tmp_path)
    assert result == []
