"""Tiered PDF converter: Marker → Docling → PyMuPDF4LLM → pdfplumber.

Each tier is tried in order; if unavailable or it raises, the next is tried.
LegacyPdfConverter (pdfplumber) is always the final fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path

from drop2md.converters import BaseConverter, ConversionError, ConverterResult
from drop2md.converters.legacy_pdf import LegacyPdfConverter

log = logging.getLogger(__name__)


class MarkerPdfConverter(BaseConverter):
    """Marker converter — best quality, supports Apple MPS/CUDA/CPU."""

    name = "marker"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import marker  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path, device: str = "mps") -> ConverterResult:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        models = create_model_dict()
        converter = PdfConverter(artifact_dict=models)
        rendered = converter(str(path))
        markdown, _, images = text_from_rendered(rendered)

        saved_images: list[Path] = []
        if images:
            img_dir = output_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            for img_name, img_data in images.items():
                dest = img_dir / f"{path.stem}_{img_name}"
                if isinstance(img_data, bytes):
                    dest.write_bytes(img_data)
                else:
                    # Newer Marker returns PIL Image objects
                    img_data.save(str(dest))
                saved_images.append(dest)

        return ConverterResult(
            markdown=markdown,
            images=saved_images,
            converter_used=self.name,
        )


class DoclingPdfConverter(BaseConverter):
    """Docling converter — excellent table support, Apache 2.0, CPU-capable."""

    name = "docling"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import docling  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()
        return ConverterResult(
            markdown=markdown,
            converter_used=self.name,
            metadata={"pages": result.document.num_pages()},
        )


class PyMuPdfConverter(BaseConverter):
    """PyMuPDF4LLM converter — lightweight, no PyTorch dependency."""

    name = "pymupdf4llm"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pymupdf4llm  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        import pymupdf4llm

        markdown = pymupdf4llm.to_markdown(str(path))
        return ConverterResult(
            markdown=markdown,
            converter_used=self.name,
        )


# Ordered from best to most widely available
_TIERS: list[type[BaseConverter]] = [
    MarkerPdfConverter,
    DoclingPdfConverter,
    PyMuPdfConverter,
    LegacyPdfConverter,
]


class TieredPdfConverter(BaseConverter):
    """Tries each PDF converter in order, falling back on failure."""

    name = "pdf"

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        for ConverterClass in _TIERS:
            if not ConverterClass.is_available():
                log.debug("PDF tier %s not available, skipping", ConverterClass.name)
                continue
            try:
                log.debug("Trying PDF tier: %s", ConverterClass.name)
                result = ConverterClass().convert(path, output_dir)
                result.converter_used = ConverterClass.name
                log.info("Converted %s via %s", path.name, ConverterClass.name)
                return result
            except Exception as exc:
                log.warning(
                    "PDF tier %s failed for %s: %s — trying next",
                    ConverterClass.name,
                    path.name,
                    exc,
                )

        raise ConversionError(f"All PDF conversion tiers exhausted for {path}")
