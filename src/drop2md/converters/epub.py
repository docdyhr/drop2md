"""EPUB to Markdown converter via pandoc."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from drop2md.converters import BaseConverter, ConversionError, ConverterResult

log = logging.getLogger(__name__)


class EpubConverter(BaseConverter):
    """Converts EPUB to GFM markdown via pandoc."""

    name = "pandoc-epub"

    @classmethod
    def is_available(cls) -> bool:
        return (
            subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        img_dir = output_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                "pandoc",
                "-f",
                "epub",
                "-t",
                "gfm",
                f"--extract-media={img_dir}",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ConversionError(f"pandoc failed: {result.stderr}")

        images = list(img_dir.rglob("*"))
        images = [i for i in images if i.is_file()]

        return ConverterResult(
            markdown=result.stdout,
            images=images,
            converter_used=self.name,
        )
