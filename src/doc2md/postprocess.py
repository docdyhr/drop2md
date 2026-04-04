"""GFM post-processing: frontmatter injection, heading normalization, cleanup."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from doc2md.converters import ConverterResult
from doc2md.utils.gfm import (
    ensure_trailing_newline,
    fix_table_alignment,
    normalize_headings,
    strip_page_markers,
)


def build_frontmatter(
    source: Path,
    result: ConverterResult,
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
        frontmatter = build_frontmatter(source, result)
        md = frontmatter + md

    return md


def _collapse_blank_lines(text: str) -> str:
    """Replace 3+ consecutive blank lines with 2."""
    return re.sub(r"\n{3,}", "\n\n", text)
