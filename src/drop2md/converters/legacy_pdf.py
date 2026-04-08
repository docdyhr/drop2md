"""Legacy PDF converter — wraps the original pdfplumber-based logic.

This is always available as a fallback when Marker/Docling/PyMuPDF are absent.

v0.3 (VEP-5): when PyMuPDF is available as a library, run an image extraction
pass so images are not silently lost at this fallback tier. The extracted images
feed into the Visual Enhancement Pipeline exactly as they would from Marker.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from drop2md.converters import BaseConverter, ConverterResult

log = logging.getLogger(__name__)


class LegacyPdfConverter(BaseConverter):
    """pdfplumber-based PDF converter. Always available — no heavy dependencies."""

    name = "pdfplumber"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pdfplumber  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        try:
            import pdfplumber
        except ImportError as exc:
            raise ImportError("pdfplumber is required: pip install pdfplumber") from exc

        md_parts: list[str] = []
        warnings: list[str] = []
        page_count = 0

        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            all_sizes: list[float] = []
            for page in pdf.pages:
                for char in page.chars or []:
                    if char.get("size"):
                        all_sizes.append(char["size"])
            avg_size = sum(all_sizes) / len(all_sizes) if all_sizes else 12.0

            for page_num, page in enumerate(pdf.pages, 1):
                md_parts.append(f"\n\n<!-- Page {page_num} -->\n")

                tables = page.extract_tables() or []
                if tables:
                    for table in tables:
                        md_parts.append("\n" + _table_to_markdown(table) + "\n")

                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if not text:
                    continue

                for line in text.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        md_parts.append("")
                        continue

                    if re.match(r"^[•·▪▸\-\*]\s+", stripped):
                        bullet_text = re.sub(r"^[•·▪▸\-\*]\s+", "", stripped)
                        md_parts.append(f"- {bullet_text}")
                        continue

                    if re.match(r"^\d+[\.\)]\s+", stripped):
                        num_text = re.sub(r"^\d+[\.\)]\s+", "", stripped)
                        m = re.match(r"^(\d+)", stripped)
                        num = m.group(1) if m else "1"
                        md_parts.append(f"{num}. {num_text}")
                        continue

                    is_head, level = _is_heading(stripped, avg_size)
                    if is_head:
                        prefix = "#" * level
                        md_parts.append(f"\n{prefix} {stripped}\n")
                        continue

                    md_parts.append(stripped)

        markdown = _clean_text("\n".join(md_parts))

        # VEP-5: opportunistic image extraction via PyMuPDF when available.
        # pdfplumber does not extract images; PyMuPDF does and may already be
        # installed as part of [pdf-light]. This makes images available to the
        # VEP pipeline without adding a hard dependency.
        images: list[Path] = []
        try:
            from drop2md.utils.image_extractor import extract_pdf_images

            images = extract_pdf_images(path, output_dir)
            if images:
                log.debug(
                    "pdfplumber tier: extracted %d image(s) via PyMuPDF", len(images)
                )
        except Exception as exc:
            log.debug("pdfplumber image pass skipped: %s", exc)

        return ConverterResult(
            markdown=markdown,
            images=images,
            converter_used=self.name,
            metadata={"pages": page_count},
            warnings=warnings,
        )


def _clean_text(text: str) -> str:
    text = re.sub(r"\(cid:\d+\)", "•", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def _is_heading(line: str, avg_size: float) -> tuple[bool, int]:
    stripped = line.strip()
    if not stripped:
        return False, 0
    if stripped.isupper() and len(stripped.split()) <= 8:
        return True, 2
    return False, 0


def _table_to_markdown(table: list[list]) -> str:
    if not table or not table[0]:
        return ""
    rows = [[str(cell or "").strip() for cell in row] for row in table]
    col_count = max(len(row) for row in rows)
    rows = [row + [""] * (col_count - len(row)) for row in rows]
    lines = []
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
