"""HTML to Markdown converter.

Primary: html2text
Fallback: pandoc subprocess
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from drop2md.converters import BaseConverter, ConversionError, ConverterResult

log = logging.getLogger(__name__)


class Html2TextConverter(BaseConverter):
    """html2text converter."""

    name = "html2text"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import html2text  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0  # no line wrapping
        h.unicode_snob = True
        h.protect_links = True

        html_content = path.read_text(encoding="utf-8", errors="replace")
        markdown = h.handle(html_content)
        return ConverterResult(
            markdown=markdown,
            converter_used=self.name,
        )


class PandocHtmlConverter(BaseConverter):
    """Pandoc subprocess fallback for HTML."""

    name = "pandoc-html"

    @classmethod
    def is_available(cls) -> bool:
        return subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            check=False,
        ).returncode == 0

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        result = subprocess.run(
            ["pandoc", "-f", "html", "-t", "gfm", str(path)],
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


class HtmlConverter(BaseConverter):
    """Routes HTML through html2text with pandoc fallback."""

    name = "html"

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        _converters: list[type[BaseConverter]] = [Html2TextConverter, PandocHtmlConverter]
        for ConverterClass in _converters:
            if not ConverterClass.is_available():
                continue
            try:
                result = ConverterClass().convert(path, output_dir)
                log.info("Converted %s via %s", path.name, ConverterClass.name)
                return result
            except Exception as exc:
                log.warning("%s failed for %s: %s", ConverterClass.name, path.name, exc)

        raise ConversionError(f"No HTML converter available for {path}")
