"""Office document converter: DOCX, PPTX, XLSX.

Primary: MarkItDown (microsoft/markitdown, MIT)
Fallback: pandoc subprocess
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from drop2md.converters import BaseConverter, ConversionError, ConverterResult

log = logging.getLogger(__name__)


class MarkItDownConverter(BaseConverter):
    """MarkItDown converter for Office formats (DOCX, PPTX, XLSX)."""

    name = "markitdown"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import markitdown  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(path))
        return ConverterResult(
            markdown=result.text_content,
            converter_used=self.name,
        )


class PandocOfficeConverter(BaseConverter):
    """Pandoc subprocess fallback for DOCX files."""

    name = "pandoc"

    @classmethod
    def is_available(cls) -> bool:
        return subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            check=False,
        ).returncode == 0

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        suffix = path.suffix.lower()
        if suffix not in {".docx", ".odt", ".rtf"}:
            raise ConversionError(f"Pandoc fallback does not support {suffix}")

        result = subprocess.run(
            ["pandoc", "-f", "docx", "-t", "gfm", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ConversionError(f"pandoc failed: {result.stderr}")
        return ConverterResult(
            markdown=result.stdout,
            converter_used=self.name,
        )


class OfficeConverter(BaseConverter):
    """Routes DOCX/PPTX/XLSX through MarkItDown with Pandoc fallback."""

    name = "office"

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        for ConverterClass in [MarkItDownConverter, PandocOfficeConverter]:
            if not ConverterClass.is_available():
                continue
            try:
                result = ConverterClass().convert(path, output_dir)
                log.info("Converted %s via %s", path.name, ConverterClass.name)
                return result
            except Exception as exc:
                log.warning("%s failed for %s: %s", ConverterClass.name, path.name, exc)

        raise ConversionError(f"No office converter available for {path}")
