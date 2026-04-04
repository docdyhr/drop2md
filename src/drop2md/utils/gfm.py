"""GFM (GitHub Flavored Markdown) helpers."""

from __future__ import annotations

import re


def normalize_headings(markdown: str) -> str:
    """Ensure at most one H1 heading; demote subsequent H1s to H2."""
    lines = markdown.splitlines()
    seen_h1 = False
    result = []
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            if seen_h1:
                line = "## " + line[2:]
            else:
                seen_h1 = True
        result.append(line)
    return "\n".join(result)


_SEP_RE = re.compile(r"^\|[-: |]+\|?\s*$")


def _is_separator(line: str) -> bool:
    return bool(_SEP_RE.match(line))


def fix_table_alignment(markdown: str) -> str:
    """Ensure GFM tables have a separator row after the header row.

    Only inserts a separator after the first row of a table block (the header).
    Data rows are never split by separators.
    """
    lines = markdown.splitlines()
    result = []
    for i, line in enumerate(lines):
        result.append(line)
        # Only act on data rows (not separator rows)
        if "|" not in line or _is_separator(line):
            continue
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        # Only insert a separator when the next line is a pipe row without one,
        # AND the previous input line was not a pipe row (i.e. this is the header).
        prev_line = lines[i - 1] if i > 0 else ""
        if ("|" in next_line and not _is_separator(next_line) and "|" not in prev_line):
            cols = max(line.count("|") - 1, 1)
            result.append("| " + " | ".join(["---"] * cols) + " |")
    return "\n".join(result)


def strip_page_markers(markdown: str) -> str:
    """Remove <!-- Page N --> comments from markdown."""
    return re.sub(r"<!--\s*Page\s+\d+\s*-->\n?", "", markdown)


def ensure_trailing_newline(markdown: str) -> str:
    """Ensure markdown ends with a single newline."""
    return markdown.rstrip("\n") + "\n"
