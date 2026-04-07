#!/usr/bin/env python3
"""
pdf_to_markdown.py — Convert PDF files to Markdown

Usage:
    python pdf_to_markdown.py input.pdf
    python pdf_to_markdown.py input.pdf -o output.md
    python pdf_to_markdown.py *.pdf          # batch convert
"""

import sys
import re
import argparse
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("Missing dependency: pip install pdfplumber")


def clean_text(text: str) -> str:
    """Clean up extracted text artifacts."""
    # Replace CID glyph placeholders (e.g. bullet chars encoded as CID)
    text = re.sub(r'\(cid:\d+\)', '•', text)
    # Normalize whitespace within lines
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]
    return '\n'.join(lines)


def is_heading(line: str, font_sizes: list[float] | None, avg_size: float) -> tuple[bool, int]:
    """Heuristic: detect headings by font size or ALL CAPS short lines."""
    stripped = line.strip()
    if not stripped:
        return False, 0

    # ALL CAPS short line (likely a heading)
    if stripped.isupper() and len(stripped.split()) <= 8:
        return True, 2

    # Font size based (if available)
    if font_sizes and avg_size:
        max_size = max(font_sizes, default=avg_size)
        if max_size > avg_size * 1.3:
            return True, 1
        elif max_size > avg_size * 1.1:
            return True, 2

    return False, 0


def table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table to Markdown table syntax."""
    if not table or not table[0]:
        return ""

    # Replace None with empty string
    rows = [[str(cell or '').strip() for cell in row] for row in table]
    col_count = max(len(row) for row in rows)

    # Pad rows to same width
    rows = [row + [''] * (col_count - len(row)) for row in rows]

    lines = []
    header = rows[0]
    lines.append('| ' + ' | '.join(header) + ' |')
    lines.append('| ' + ' | '.join(['---'] * col_count) + ' |')
    for row in rows[1:]:
        lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(lines)


def pdf_to_markdown(pdf_path: Path) -> str:
    """Extract and convert a PDF to Markdown string."""
    md_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        # Gather global font size stats for heading detection
        all_sizes = []
        for page in pdf.pages:
            for char in (page.chars or []):
                if char.get('size'):
                    all_sizes.append(char['size'])
        avg_size = sum(all_sizes) / len(all_sizes) if all_sizes else 12.0

        for page_num, page in enumerate(pdf.pages, 1):
            md_parts.append(f'\n\n---\n<!-- Page {page_num} -->\n')

            # Extract tables first (to avoid double-processing their text)
            tables = page.extract_tables() or []
            table_bboxes = []
            for table_obj in page.find_tables():
                table_bboxes.append(table_obj.bbox)

            if tables:
                for table in tables:
                    md_parts.append('\n' + table_to_markdown(table) + '\n')

            # Extract text (excluding table regions if possible)
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if not text:
                continue

            lines = text.splitlines()
            in_list = False

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if in_list:
                        in_list = False
                    md_parts.append('')
                    continue

                # Detect bullet lists
                if re.match(r'^[•·▪▸\-\*]\s+', stripped):
                    bullet_text = re.sub(r'^[•·▪▸\-\*]\s+', '', stripped)
                    md_parts.append(f'- {bullet_text}')
                    in_list = True
                    continue

                # Detect numbered lists
                if re.match(r'^\d+[\.\)]\s+', stripped):
                    num_text = re.sub(r'^\d+[\.\)]\s+', '', stripped)
                    num = re.match(r'^(\d+)', stripped).group(1)
                    md_parts.append(f'{num}. {num_text}')
                    in_list = True
                    continue

                # Heading detection
                is_head, level = is_heading(stripped, None, avg_size)
                if is_head:
                    prefix = '#' * level
                    md_parts.append(f'\n{prefix} {stripped}\n')
                    continue

                md_parts.append(stripped)

    return clean_text('\n'.join(md_parts))


def convert(input_path: Path, output_path: Path | None = None) -> Path:
    print(f"Converting: {input_path.name}", end=' ... ', flush=True)
    md_content = pdf_to_markdown(input_path)

    out = output_path or input_path.with_suffix('.md')
    out.write_text(md_content, encoding='utf-8')
    print(f"→ {out.name}")
    return out


def main():
    parser = argparse.ArgumentParser(description='Convert PDF to Markdown')
    parser.add_argument('files', nargs='+', type=Path, help='PDF file(s) to convert')
    parser.add_argument('-o', '--output', type=Path, help='Output .md file (single file only)')
    args = parser.parse_args()

    if args.output and len(args.files) > 1:
        sys.exit("Error: -o/--output can only be used with a single input file.")

    for pdf_path in args.files:
        if not pdf_path.exists():
            print(f"Warning: {pdf_path} not found, skipping.")
            continue
        if pdf_path.suffix.lower() != '.pdf':
            print(f"Warning: {pdf_path} is not a .pdf, skipping.")
            continue
        convert(pdf_path, args.output if len(args.files) == 1 else None)


if __name__ == '__main__':
    main()
