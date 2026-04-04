"""Route documents to the appropriate converter based on MIME type.

Uses python-magic for MIME detection (more reliable than extension alone).
Falls back to extension-based routing if magic is unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from drop2md.converters import BaseConverter, ConversionError, ConverterResult
from drop2md.converters.epub import EpubConverter
from drop2md.converters.html import HtmlConverter
from drop2md.converters.image import ImageConverter
from drop2md.converters.office import OfficeConverter
from drop2md.converters.pdf import TieredPdfConverter

log = logging.getLogger(__name__)

# MIME type → converter class
_MIME_MAP: dict[str, type[BaseConverter]] = {
    "application/pdf": TieredPdfConverter,
    # Office
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": OfficeConverter,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": OfficeConverter,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": OfficeConverter,
    "application/msword": OfficeConverter,
    "application/vnd.ms-powerpoint": OfficeConverter,
    "application/vnd.ms-excel": OfficeConverter,
    # HTML
    "text/html": HtmlConverter,
    # EPUB
    "application/epub+zip": EpubConverter,
    # Images
    "image/png": ImageConverter,
    "image/jpeg": ImageConverter,
    "image/gif": ImageConverter,
    "image/webp": ImageConverter,
    "image/tiff": ImageConverter,
}

# Extension fallback map
_EXT_MAP: dict[str, type[BaseConverter]] = {
    ".pdf": TieredPdfConverter,
    ".docx": OfficeConverter,
    ".pptx": OfficeConverter,
    ".xlsx": OfficeConverter,
    ".doc": OfficeConverter,
    ".ppt": OfficeConverter,
    ".xls": OfficeConverter,
    ".html": HtmlConverter,
    ".htm": HtmlConverter,
    ".epub": EpubConverter,
    ".png": ImageConverter,
    ".jpg": ImageConverter,
    ".jpeg": ImageConverter,
    ".gif": ImageConverter,
    ".webp": ImageConverter,
    ".tiff": ImageConverter,
    ".tif": ImageConverter,
}

# Extensions to silently ignore (already markdown, hidden files, etc.)
_IGNORE_EXTS = {".md", ".tmp", ".lock", ".log", ".DS_Store", ""}


def _detect_mime(path: Path) -> str | None:
    try:
        import magic

        return magic.from_file(str(path), mime=True)
    except (ImportError, Exception) as exc:
        log.debug("MIME detection unavailable: %s — using extension fallback", exc)
        return None


def get_converter(path: Path) -> type[BaseConverter] | None:
    """Return the appropriate converter class for *path*, or None if unsupported."""
    if path.suffix.lower() in _IGNORE_EXTS:
        return None

    mime = _detect_mime(path)
    if mime and mime in _MIME_MAP:
        return _MIME_MAP[mime]

    return _EXT_MAP.get(path.suffix.lower())


def dispatch(path: Path, output_dir: Path) -> ConverterResult:
    """Detect format and run the appropriate converter for *path*.

    Args:
        path: Absolute path to the source document.
        output_dir: Directory where output .md and images should be written.

    Returns:
        ConverterResult

    Raises:
        ConversionError: If no suitable converter is found or all fail.
    """
    converter_class = get_converter(path)
    if converter_class is None:
        raise ConversionError(
            f"No converter registered for {path.suffix!r} ({path.name})"
        )

    log.info("Dispatching %s → %s", path.name, converter_class.name)
    return converter_class().convert(path, output_dir)
