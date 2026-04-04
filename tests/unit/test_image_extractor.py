"""Unit tests for image_extractor — PyMuPDF calls are mocked."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc2md.utils.image_extractor import extract_pdf_images, inject_image_references

# ─── inject_image_references ─────────────────────────────────────────────────

@pytest.mark.unit
def test_inject_empty_list_is_noop():
    """No images → markdown is returned unchanged."""
    md = "# Hello\n\nSome text."
    assert inject_image_references(md, [], Path("/any")) == md


@pytest.mark.unit
def test_inject_appends_relative_ref(tmp_path):
    """Image inside base_dir produces a relative ./images/... reference."""
    img = tmp_path / "images" / "doc_1_0.png"
    img.parent.mkdir()
    img.write_bytes(b"fake")

    result = inject_image_references("# Hello", [img], tmp_path)
    assert "![" in result
    assert "./images/doc_1_0.png" in result


@pytest.mark.unit
def test_inject_alt_text_from_stem(tmp_path):
    """Alt text is derived from the image stem (underscores → spaces)."""
    img = tmp_path / "images" / "page_1_chart.png"
    img.parent.mkdir()
    img.write_bytes(b"fake")

    result = inject_image_references("text", [img], tmp_path)
    assert "![page 1 chart]" in result


@pytest.mark.unit
def test_inject_multiple_images(tmp_path):
    """All images in the list are appended as separate refs."""
    (tmp_path / "images").mkdir()
    imgs = [tmp_path / "images" / f"img_{i}.png" for i in range(3)]
    for img in imgs:
        img.write_bytes(b"fake")

    result = inject_image_references("text", imgs, tmp_path)
    assert result.count("![") == 3


@pytest.mark.unit
def test_inject_image_outside_base_uses_fallback(tmp_path):
    """Image whose path cannot be made relative to base_dir uses images/{name}."""
    other = tmp_path / "elsewhere" / "chart.png"
    other.parent.mkdir()
    other.write_bytes(b"fake")
    base = tmp_path / "base"
    base.mkdir()

    result = inject_image_references("text", [other], base)
    assert "images/chart.png" in result


# ─── extract_pdf_images — PyMuPDF unavailable ─────────────────────────────────

@pytest.mark.unit
def test_extract_returns_empty_when_pymupdf_missing(tmp_path):
    """Gracefully returns [] when PyMuPDF (fitz) is not installed."""
    with patch.dict(sys.modules, {"fitz": None}):
        result = extract_pdf_images(tmp_path / "test.pdf", tmp_path)
    assert result == []


@pytest.mark.unit
def test_extract_creates_images_dir(tmp_path):
    """The images/ subdirectory is always created, even if no images are found."""
    with patch.dict(sys.modules, {"fitz": None}):
        extract_pdf_images(tmp_path / "test.pdf", tmp_path)
    assert (tmp_path / "images").is_dir()


# ─── extract_pdf_images — PyMuPDF available ───────────────────────────────────

@pytest.mark.unit
def test_extract_saves_images_from_pdf(tmp_path):
    """Images returned by PyMuPDF are written to output_dir/images/."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"fake pdf")

    mock_page = MagicMock()
    mock_page.get_images.return_value = [(42, 0, 0, 0, 0, "", "")]  # xref=42

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.extract_image.return_value = {"image": b"\x89PNG", "ext": "png"}

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        saved = extract_pdf_images(pdf, tmp_path)

    assert len(saved) == 1
    assert saved[0].suffix == ".png"
    assert saved[0].read_bytes() == b"\x89PNG"
    mock_doc.close.assert_called_once()


@pytest.mark.unit
def test_extract_skips_bad_image_xref(tmp_path):
    """If extract_image raises for one xref, it is skipped; others are saved."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"fake pdf")

    mock_page = MagicMock()
    mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "", ""), (2, 0, 0, 0, 0, "", "")]

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.extract_image.side_effect = [
        RuntimeError("bad xref"),
        {"image": b"\x89PNG", "ext": "png"},
    ]

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        saved = extract_pdf_images(pdf, tmp_path)

    # First xref failed, second succeeded
    assert len(saved) == 1
