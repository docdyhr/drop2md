"""Unit tests for the EPUB converter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConversionError
from drop2md.converters.epub import EpubConverter


@pytest.mark.unit
def test_epub_is_available_when_pandoc_present():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        assert EpubConverter.is_available() is True


@pytest.mark.unit
def test_epub_is_not_available_when_pandoc_missing():
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch("subprocess.run", return_value=mock_result):
        assert EpubConverter.is_available() is False


@pytest.mark.unit
def test_epub_convert_success(tmp_path):
    """EpubConverter calls pandoc and returns a ConverterResult."""
    epub = tmp_path / "book.epub"
    epub.touch()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "# Chapter 1\n\nContent here.\n"

    with patch("subprocess.run", return_value=mock_result):
        result = EpubConverter().convert(epub, tmp_path)

    assert "Chapter 1" in result.markdown
    assert result.converter_used == "pandoc-epub"


@pytest.mark.unit
def test_epub_convert_failure(tmp_path):
    """EpubConverter raises ConversionError when pandoc returns non-zero."""
    epub = tmp_path / "bad.epub"
    epub.touch()

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "pandoc: cannot read epub"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(ConversionError, match="pandoc failed"),
    ):
        EpubConverter().convert(epub, tmp_path)


@pytest.mark.unit
def test_epub_convert_with_images(tmp_path):
    """EpubConverter includes extracted image files in the result."""
    epub = tmp_path / "illustrated.epub"
    epub.touch()

    img_dir = tmp_path / "images"
    img_dir.mkdir()
    (img_dir / "cover.png").write_bytes(b"PNG")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "# Book\n\n![cover](images/cover.png)\n"

    with patch("subprocess.run", return_value=mock_result):
        result = EpubConverter().convert(epub, tmp_path)

    assert any(p.name == "cover.png" for p in result.images)
