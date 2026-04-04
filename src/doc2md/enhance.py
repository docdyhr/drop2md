"""AI enhancement pipeline for doc2md.

Provides image captioning and GFM table validation via any configured AI provider.
Uses make_provider() to route to Ollama, Claude, OpenAI, or HuggingFace.

All calls are wrapped in try/except — provider being offline never blocks conversion.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from doc2md.config import Config
from doc2md.converters import ConverterResult
from doc2md.enhance_providers import make_provider

log = logging.getLogger(__name__)


def describe_image(image_path: Path, config: Config) -> str:
    """Generate a concise alt-text description for an image.

    Returns empty string on failure (provider offline or error).
    """
    try:
        provider = make_provider(config)
        prompt = (
            "/no_think "
            "Describe this image from a document in one concise sentence "
            "suitable for use as Markdown alt-text. Be specific and factual."
        )
        return provider.generate(prompt, image_path)
    except Exception as exc:
        log.debug("Image description failed for %s: %s", image_path.name, exc)
        return ""


def validate_table(table_md: str, config: Config) -> str:
    """Ask the AI provider to validate and fix a GFM table.

    Returns the original table if provider is unavailable or returns nonsense.
    """
    try:
        provider = make_provider(config)
        prompt = (
            "/no_think "
            "Fix this GitHub Flavored Markdown table so it is valid GFM. "
            "Return ONLY the corrected table, no explanation:\n\n"
            f"{table_md}"
        )
        fixed = provider.generate(prompt)
        if "|" in fixed:
            return fixed
        return table_md
    except Exception as exc:
        log.debug("Table validation failed: %s", exc)
        return table_md


def _inject_image_captions(markdown: str, images: list[Path], config: Config) -> str:
    """Replace bare image refs with AI-generated alt-text."""
    for img_path in images:
        old_ref = f"![](./{img_path.parent.name}/{img_path.name})"
        alt = describe_image(img_path, config)
        if alt:
            new_ref = f"![{alt}](./{img_path.parent.name}/{img_path.name})"
            markdown = markdown.replace(old_ref, new_ref)
    return markdown


def _enhance_tables(markdown: str, config: Config) -> str:
    """Find and validate GFM tables in markdown."""
    table_pattern = re.compile(
        r"(\|[^\n]+\|\n)(\|[-:| ]+\|\n)((?:\|[^\n]+\|\n)+)",
        re.MULTILINE,
    )

    def _fix_match(m: re.Match) -> str:
        return validate_table(m.group(0), config)

    return table_pattern.sub(_fix_match, markdown)


def enhance(result: ConverterResult, config: Config) -> ConverterResult:
    """Apply AI enhancement to a ConverterResult.

    - Adds alt-text to images that have empty alt attributes
    - Validates and fixes broken GFM tables

    Returns a new ConverterResult with enhanced markdown.
    """
    if not config.ollama.enabled:
        return result

    md = result.markdown

    if result.images:
        md = _inject_image_captions(md, result.images, config)

    if "|" in md:
        md = _enhance_tables(md, config)

    return ConverterResult(
        markdown=md,
        images=result.images,
        metadata=result.metadata,
        converter_used=result.converter_used,
        warnings=result.warnings,
    )
