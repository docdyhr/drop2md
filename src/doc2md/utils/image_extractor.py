"""Extract embedded images from PDF files using pdfplumber/PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def extract_pdf_images(pdf_path: Path, output_dir: Path) -> list[Path]:
    """Extract all embedded images from a PDF and save to *output_dir/images/*.

    Returns list of saved image paths. Falls back gracefully if pymupdf unavailable.
    """
    img_dir = output_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        for page_num, page in enumerate(doc, 1):
            for img_idx, img_ref in enumerate(page.get_images(full=True)):
                xref = img_ref[0]
                try:
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image["image"]
                    ext = base_image.get("ext", "png")
                    dest = img_dir / f"{pdf_path.stem}_{page_num}_{img_idx}.{ext}"
                    dest.write_bytes(img_bytes)
                    saved.append(dest)
                except Exception as exc:
                    log.debug("Could not extract image xref=%d: %s", xref, exc)
        doc.close()
    except ImportError:
        log.debug("PyMuPDF not available — skipping image extraction")

    return saved


def inject_image_references(markdown: str, images: list[Path], base_dir: Path) -> str:
    """Append image references to markdown if not already present."""
    if not images:
        return markdown

    refs: list[str] = []
    for img_path in images:
        try:
            rel = img_path.relative_to(base_dir)
            rel_str = str(rel)
        except ValueError:
            rel_str = f"images/{img_path.name}"
        alt = img_path.stem.replace("_", " ").strip()
        refs.append(f"![{alt}](./{rel_str})")

    return markdown.rstrip("\n") + "\n\n" + "\n".join(refs) + "\n"
