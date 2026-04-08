"""Unit tests for the file dispatcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from drop2md.converters.epub import EpubConverter
from drop2md.converters.html import HtmlConverter
from drop2md.converters.image import ImageConverter
from drop2md.converters.office import OfficeConverter
from drop2md.converters.pdf import TieredPdfConverter
from drop2md.dispatcher import get_converter


@pytest.mark.unit
@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.pdf", TieredPdfConverter),
        ("REPORT.PDF", TieredPdfConverter),
        ("notes.docx", OfficeConverter),
        ("slides.pptx", OfficeConverter),
        ("data.xlsx", OfficeConverter),
        ("page.html", HtmlConverter),
        ("page.htm", HtmlConverter),
        ("book.epub", EpubConverter),
        ("photo.png", ImageConverter),
        ("photo.jpg", ImageConverter),
        ("photo.jpeg", ImageConverter),
    ],
)
def test_extension_routing(filename: str, expected: type, tmp_path: Path):
    """Extension-based routing should return the correct converter class."""
    path = tmp_path / filename
    path.touch()

    # Disable MIME detection to test extension fallback
    with patch("drop2md.dispatcher._detect_mime", return_value=None):
        result = get_converter(path)

    assert result is expected, f"Expected {expected.name} for {filename}, got {result}"


@pytest.mark.unit
def test_ignore_md_files(tmp_path: Path):
    path = tmp_path / "already.md"
    path.touch()
    assert get_converter(path) is None


@pytest.mark.unit
def test_ignore_tmp_files(tmp_path: Path):
    path = tmp_path / "file.tmp"
    path.touch()
    assert get_converter(path) is None


@pytest.mark.unit
def test_unknown_extension_returns_none(tmp_path: Path):
    path = tmp_path / "data.xyz"
    path.touch()
    with patch("drop2md.dispatcher._detect_mime", return_value=None):
        assert get_converter(path) is None


@pytest.mark.unit
def test_mime_type_overrides_extension(tmp_path: Path):
    """A file named .txt that is actually a PDF by MIME should route to PDF converter."""
    path = tmp_path / "document.txt"
    path.touch()
    with patch("drop2md.dispatcher._detect_mime", return_value="application/pdf"):
        result = get_converter(path)
    assert result is TieredPdfConverter


# ─── Q-5: RTF / ODT routing ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "filename",
    ["document.rtf", "document.odt", "slides.odp", "spreadsheet.ods"],
)
def test_rtf_odt_extension_routing(filename: str, tmp_path: Path):
    """RTF and ODF files route to OfficeConverter via extension fallback."""
    path = tmp_path / filename
    path.touch()
    with patch("drop2md.dispatcher._detect_mime", return_value=None):
        result = get_converter(path)
    assert result is OfficeConverter, (
        f"Expected OfficeConverter for {filename}, got {result}"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "mime",
    [
        "application/rtf",
        "text/rtf",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.spreadsheet",
    ],
)
def test_rtf_odt_mime_routing(mime: str, tmp_path: Path):
    """RTF and ODF MIME types route to OfficeConverter."""
    path = tmp_path / "document.bin"
    path.touch()
    with patch("drop2md.dispatcher._detect_mime", return_value=mime):
        result = get_converter(path)
    assert result is OfficeConverter, f"Expected OfficeConverter for MIME {mime!r}"
