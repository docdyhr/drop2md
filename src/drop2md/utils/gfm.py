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


# ---------------------------------------------------------------------------
# Deterministic markdown polish (no AI required)
# ---------------------------------------------------------------------------

_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n([a-z])")
_SENTENCE_GAP_RE = re.compile(r"(?<=[a-z]{3}[.!?])([A-Z])")
_REPEATED_WORD_RE = re.compile(r"\b([a-zA-Z]{3,})([ \t]+\1)+\b", re.IGNORECASE)


def fix_hyphen_line_breaks(text: str) -> str:
    """Rejoin words hyphenated across line breaks from PDF column layout.

    Converts ``docu-\\nment`` → ``docu-ment``.  Only fires when the second
    fragment starts with a lowercase letter to avoid touching real abbreviations
    like ``EU-\\nUS`` or list markers.  The hyphen is always kept — we can't
    reliably know whether ``some-\\nthing`` was ``something`` or ``some-thing``.
    """
    return _HYPHEN_BREAK_RE.sub(r"\1-\2", text)


def fix_sentence_spacing(text: str) -> str:
    """Insert a missing space between a sentence-ending punctuation and the next word.

    Corrects ``end.Start`` → ``end. Start``.  The lookbehind requires at least
    three lowercase letters before the punctuation mark to avoid triggering on
    common abbreviations such as ``Dr.`` or ``Fig.``.  Lines starting with
    spaces (code blocks), backticks, or containing ``://`` (URLs) are skipped.
    """
    lines = text.splitlines(keepends=True)
    result = []
    in_code_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
        if in_code_fence or stripped.startswith("    ") or "://" in line:
            result.append(line)
        else:
            result.append(_SENTENCE_GAP_RE.sub(r" \1", line))
    return "".join(result)


def fix_repeated_words(text: str) -> str:
    """Remove adjacent duplicate words caused by PDF extraction boundary artifacts.

    ``the the book`` → ``the book``.  Only matches words of 3+ characters to
    avoid removing intentional repetition in informal prose (``ha ha``,
    ``bye bye``).  Case-insensitive so ``The the`` is also caught.
    """
    return _REPEATED_WORD_RE.sub(r"\1", text)
