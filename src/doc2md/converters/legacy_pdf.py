"""Legacy PDF converter — wraps the original pdfplumber-based logic.

This is always available as a fallback when Marker/Docling/PyMuPDF are absent.
The original standalone script (pdf_to_markdown.py) is preserved in the project root.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc2md.converters import BaseConverter, ConverterResult


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

                lines = text.splitlines()
                in_list = False

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        in_list = False
                        md_parts.append("")
                        continue

                    if re.match(r"^[•·▪▸\-\*]\s+", stripped):
                        bullet_text = re.sub(r"^[•·▪▸\-\*]\s+", "", stripped)
                        md_parts.append(f"- {bullet_text}")
                        in_list = True
                        continue

                    if re.match(r"^\d+[\.\)]\s+", stripped):
                        num_text = re.sub(r"^\d+[\.\)]\s+", "", stripped)
                        m = re.match(r"^(\d+)", stripped)
                        num = m.group(1) if m else "1"
                        md_parts.append(f"{num}. {num_text}")
                        in_list = True
                        continue

                    is_head, level = _is_heading(stripped, avg_size)
                    if is_head:
                        prefix = "#" * level
                        md_parts.append(f"\n{prefix} {stripped}\n")
                        continue

                    md_parts.append(stripped)

        markdown = _clean_text("\n".join(md_parts))
        return ConverterResult(
            markdown=markdown,
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
