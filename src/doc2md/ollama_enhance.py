"""Optional Ollama AI enhancement for converted documents.

Provides image captioning (alt-text generation) and GFM table validation.
All calls are wrapped in try/except — Ollama being offline never blocks conversion.
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

import httpx

from doc2md.config import Config
from doc2md.converters import ConverterResult

log = logging.getLogger(__name__)


def _generate(prompt: str, config: Config, image_path: Path | None = None) -> str:
    """Send a prompt (optionally with an image) to Ollama and return the response."""
    payload: dict = {
        "model": config.ollama.model,
        "prompt": prompt,
        "stream": False,
    }
    if image_path and image_path.exists():
        img_b64 = base64.b64encode(image_path.read_bytes()).decode()
        payload["images"] = [img_b64]

    resp = httpx.post(
        f"{config.ollama.base_url}/api/generate",
        json=payload,
        timeout=config.ollama.timeout_seconds,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def describe_image(image_path: Path, config: Config) -> str:
    """Generate a concise alt-text description for an image.

    Returns empty string on failure (Ollama offline or model error).
    """
    try:
        prompt = (
            "Describe this image from a document in one concise sentence "
            "suitable for use as Markdown alt-text. Be specific and factual."
        )
        return _generate(prompt, config, image_path)
    except Exception as exc:
        log.debug("Image description failed for %s: %s", image_path.name, exc)
        return ""


def validate_table(table_md: str, config: Config) -> str:
    """Ask Ollama to validate and fix a GFM table.

    Returns the original table if Ollama is unavailable or returns nonsense.
    """
    try:
        prompt = (
            "Fix this GitHub Flavored Markdown table so it is valid GFM. "
            "Return ONLY the corrected table, no explanation:\n\n"
            f"{table_md}"
        )
        fixed = _generate(prompt, config)
        # Sanity check: result should still look like a table
        if "|" in fixed:
            return fixed
        return table_md
    except Exception as exc:
        log.debug("Table validation failed: %s", exc)
        return table_md


def _inject_image_captions(markdown: str, images: list[Path], config: Config) -> str:
    """Replace bare image refs with Ollama-generated alt-text."""
    for img_path in images:
        old_ref = f"![](./{img_path.parent.name}/{img_path.name})"
        alt = describe_image(img_path, config)
        if alt:
            new_ref = f"![{alt}](./{img_path.parent.name}/{img_path.name})"
            markdown = markdown.replace(old_ref, new_ref)
    return markdown


def _enhance_tables(markdown: str, config: Config) -> str:
    """Find and validate GFM tables in markdown."""
    # Match multi-line pipe table blocks
    table_pattern = re.compile(
        r"(\|[^\n]+\|\n)(\|[-:| ]+\|\n)((?:\|[^\n]+\|\n)+)",
        re.MULTILINE,
    )
    def _fix_match(m: re.Match) -> str:
        table = m.group(0)
        return validate_table(table, config)

    return table_pattern.sub(_fix_match, markdown)


def enhance(result: ConverterResult, config: Config) -> ConverterResult:
    """Apply Ollama enhancement to a ConverterResult.

    - Adds alt-text to images that have empty alt attributes
    - Validates and fixes broken GFM tables

    Returns a new ConverterResult with enhanced markdown.
    """
    if not config.ollama.enabled:
        return result

    md = result.markdown

    # Image captions for extracted images with no alt-text
    if result.images:
        md = _inject_image_captions(md, result.images, config)

    # Table validation (only if tables present)
    if "|" in md:
        md = _enhance_tables(md, config)

    return ConverterResult(
        markdown=md,
        images=result.images,
        metadata=result.metadata,
        converter_used=result.converter_used,
        warnings=result.warnings,
    )
