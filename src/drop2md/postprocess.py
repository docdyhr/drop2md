"""GFM post-processing: frontmatter injection, heading normalization, cleanup."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from drop2md.converters import ConverterResult
from drop2md.utils.gfm import (
    ensure_trailing_newline,
    fix_table_alignment,
    normalize_headings,
    strip_page_markers,
)

# ---------------------------------------------------------------------------
# Quality scoring (Q-1)
# ---------------------------------------------------------------------------

# Minimum word counts to be considered medium or high quality
_WORDS_MEDIUM = 100
_WORDS_HIGH = 400


def score_quality(markdown: str, result: ConverterResult) -> str:
    """Return a quality label: 'high' | 'medium' | 'low'.

    Computed purely from structural signals — no AI required.

    Scoring factors:
    - Word count: proxy for content richness
    - Heading density: well-structured documents have headings
    - Image ref count: extracted images preserved in output
    - Warning count: converter warnings indicate degraded output
    - Scanned-PDF flag in warnings: strong signal for low quality
    """
    text = markdown.strip()
    words = len(text.split())

    headings = len(re.findall(r"^#{1,6} ", text, re.MULTILINE))
    image_refs = len(re.findall(r"!\[", text))
    warning_count = len(result.warnings or [])
    is_scanned = any("Scanned PDF" in w for w in (result.warnings or []))

    # Hard low-quality signals
    if is_scanned or warning_count >= 3 or words < _WORDS_MEDIUM:
        return "low"

    # High quality: rich content, structured, no warnings
    if words >= _WORDS_HIGH and headings >= 2 and warning_count == 0:
        return "high"

    # Medium: decent word count, at least some structure or images
    if words >= _WORDS_MEDIUM and (headings >= 1 or image_refs >= 1 or warning_count <= 1):
        return "medium"

    return "low"


def build_frontmatter(
    source: Path,
    result: ConverterResult,
    quality: str | None = None,
) -> str:
    """Build a YAML frontmatter block."""
    lines = [
        "---",
        f'source: "{source.name}"',
        f'converted: "{datetime.now().isoformat(timespec="seconds")}"',
        f'converter: "{result.converter_used}"',
    ]
    if pages := result.metadata.get("pages"):
        lines.append(f"pages: {pages}")
    if quality:
        lines.append(f"quality: {quality}")
    if result.warnings:
        lines.append("warnings:")
        for w in result.warnings:
            lines.append(f'  - "{w}"')
    lines.append("---\n")
    return "\n".join(lines)


def postprocess(
    result: ConverterResult,
    source: Path,
    add_frontmatter: bool = True,
    preserve_page_markers: bool = False,
) -> str:
    """Apply GFM cleanup and optional frontmatter to a ConverterResult.

    Args:
        result: Raw converter output.
        source: Original source file path (used in frontmatter).
        add_frontmatter: Whether to prepend YAML frontmatter.
        preserve_page_markers: If False, strip <!-- Page N --> comments.

    Returns:
        Final markdown string ready to write to disk.
    """
    md = result.markdown

    if not preserve_page_markers:
        md = strip_page_markers(md)

    md = fix_table_alignment(md)
    md = normalize_headings(md)
    md = _collapse_blank_lines(md)
    md = ensure_trailing_newline(md)

    if add_frontmatter:
        quality = score_quality(md, result)
        frontmatter = build_frontmatter(source, result, quality=quality)
        md = frontmatter + md

    return str(md)


def _collapse_blank_lines(text: str) -> str:
    """Replace 3+ consecutive blank lines with 2."""
    return re.sub(r"\n{3,}", "\n\n", text)
