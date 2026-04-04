"""Image converter — OCR via pytesseract + optional Ollama vision description."""

from __future__ import annotations

import logging
from pathlib import Path

from doc2md.converters import BaseConverter, ConversionError, ConverterResult

log = logging.getLogger(__name__)


class ImageConverter(BaseConverter):
    """Converts image files to markdown using OCR and/or Ollama vision."""

    name = "image-ocr"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        warnings: list[str] = []
        markdown_parts: list[str] = []

        # Copy source image to output images dir so it can be referenced
        img_dir = output_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        dest_image = img_dir / path.name
        if not dest_image.exists():
            import shutil

            shutil.copy2(path, dest_image)

        # OCR
        ocr_text = ""
        if ImageConverter.is_available():
            try:
                import pytesseract
                from PIL import Image

                img = Image.open(path)
                ocr_text = pytesseract.image_to_string(img).strip()
            except Exception as exc:
                warnings.append(f"OCR failed: {exc}")
        else:
            warnings.append("pytesseract not available — install [ocr] extra")

        # Image reference
        rel_path = f"./images/{path.name}"
        markdown_parts.append(f"![{path.stem}]({rel_path})\n")

        if ocr_text:
            markdown_parts.append(f"\n**OCR Text:**\n\n```\n{ocr_text}\n```\n")
        else:
            markdown_parts.append("\n*No OCR text extracted.*\n")

        return ConverterResult(
            markdown="\n".join(markdown_parts),
            images=[dest_image],
            converter_used=self.name,
            warnings=warnings,
        )
