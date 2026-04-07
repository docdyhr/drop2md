"""Tiered PDF converter: Marker → Docling → PyMuPDF4LLM → pdfplumber.

Each tier is tried in order; if unavailable or it raises, the next is tried.
LegacyPdfConverter (pdfplumber) is always the final fallback.

Page-level partial recovery (Q-4): pdfplumber extracts text page-by-page.
When a top tier produces an empty or very short result that looks like a
partial failure, the pdfplumber pages for which the top-tier produced no
content are appended to the output.
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

# ML-based text converters that produce garbage output on scanned (image-only) PDFs
_TEXT_ONLY_TIERS: frozenset[type[BaseConverter]] = frozenset(
    {MarkerPdfConverter, DoclingPdfConverter}
)


def _is_scanned_pdf(path: Path, sample_pages: int = 3, char_threshold: int = 20) -> bool:
    """Return True if the PDF appears to be image-only (scanned).

    Samples the first *sample_pages* pages via pdfplumber (always available).
    If the total extracted character count is below *char_threshold* the PDF
    is treated as scanned and text-based ML converters will be skipped.
    """
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = pdf.pages[:sample_pages]
            if not pages:
                return False
            total_chars = sum(len(p.extract_text() or "") for p in pages)
            return total_chars < char_threshold
    except Exception as exc:
        log.debug("Scanned-PDF detection failed for %s: %s — assuming not scanned", path.name, exc)
        return False


class TieredPdfConverter(BaseConverter):
    """Tries each PDF converter in order, falling back on failure.

    When the PDF is detected as scanned (image-only, < 20 characters across
    the first 3 pages) the ML text-based tiers (Marker, Docling) are skipped
    because they produce garbage output on pages with no embedded text.
    PyMuPDF4LLM and pdfplumber are still tried; a warning is added to the
    result so downstream tooling can surface the degraded quality.
    """

    name = "pdf"

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        scanned = _is_scanned_pdf(path)
        if scanned:
            log.info(
                "Scanned PDF detected: %s — skipping ML text-based converters", path.name
            )

        for ConverterClass in _TIERS:
            if scanned and ConverterClass in _TEXT_ONLY_TIERS:
                log.debug("Skipping %s for scanned PDF: %s", ConverterClass.name, path.name)
                continue
            if not ConverterClass.is_available():
                log.debug("PDF tier %s not available, skipping", ConverterClass.name)
                continue
            try:
                log.debug("Trying PDF tier: %s", ConverterClass.name)
                result = ConverterClass().convert(path, output_dir)
                result.converter_used = ConverterClass.name
                if scanned:
                    result.warnings = list(result.warnings or []) + [
                        "Scanned PDF detected — text extraction may be incomplete. "
                        "Enable OCR or a vision-LLM provider for best results."
                    ]
                # Q-4: attempt page-level recovery for ML tiers that may miss pages
                if ConverterClass in _TEXT_ONLY_TIERS:
                    result = _partial_recover(result, path, output_dir)
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


def _partial_recover(
    primary: ConverterResult,
    path: Path,
    output_dir: Path,
    min_chars_per_page: int = 50,
) -> ConverterResult:
    """Attempt page-level partial recovery using pdfplumber.

    If *primary* produced very little text (fewer than *min_chars_per_page*
    characters per page on average), extract individual pages with pdfplumber
    and append any page that contributed text the primary tier missed.

    Returns the original result if recovery is not needed or not possible.
    """
    pages_meta = primary.metadata.get("pages")
    if not pages_meta:
        return primary

    primary_chars = len(primary.markdown.strip())
    avg_chars = primary_chars / pages_meta if pages_meta else primary_chars

    if avg_chars >= min_chars_per_page:
        return primary  # primary output looks healthy — no recovery needed

    log.info(
        "Partial recovery: %s produced %.0f chars/page — augmenting with pdfplumber",
        primary.converter_used, avg_chars,
    )

    try:
        import pdfplumber

        recovered_pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = (page.extract_text() or "").strip()
                if len(page_text) >= min_chars_per_page:
                    recovered_pages.append(
                        f"<!-- Page {page_num} -->\n\n{page_text}"
                    )

        if not recovered_pages:
            return primary

        # Only append pages whose content doesn't appear in the primary output
        new_pages = [
            p for p in recovered_pages
            if p.split("\n\n", 1)[-1][:40] not in primary.markdown
        ]
        if not new_pages:
            return primary

        combined = primary.markdown.rstrip() + "\n\n" + "\n\n".join(new_pages) + "\n"
        warning = (
            f"Partial recovery: {primary.converter_used} produced sparse output "
            f"({avg_chars:.0f} chars/page avg); {len(new_pages)} page(s) recovered via pdfplumber"
        )
        log.warning(warning)

        return ConverterResult(
            markdown=combined,
            images=primary.images,
            converter_used=primary.converter_used,
            metadata=primary.metadata,
            warnings=list(primary.warnings or []) + [warning],
        )
    except Exception as exc:
        log.debug("Partial recovery failed: %s", exc)
        return primary
