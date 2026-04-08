"""Unit tests for GFM postprocessing."""

from __future__ import annotations

import pytest

from drop2md.converters import ConverterResult
from drop2md.postprocess import postprocess
from drop2md.utils.gfm import (
    ensure_trailing_newline,
    fix_hyphen_line_breaks,
    fix_repeated_words,
    fix_sentence_spacing,
    fix_table_alignment,
    normalize_headings,
    strip_page_markers,
)


@pytest.mark.unit
def test_strip_page_markers():
    md = "<!-- Page 1 -->\nText\n<!-- Page 2 -->\nMore"
    result = strip_page_markers(md)
    assert "<!-- Page" not in result
    assert "Text" in result


@pytest.mark.unit
def test_normalize_headings_single_h1():
    md = "# Title\n## Section\n### Subsection"
    result = normalize_headings(md)
    assert result.count("\n# ") == 0  # Only first line starts the doc
    assert "# Title" in result


@pytest.mark.unit
def test_normalize_headings_deduplicates_h1():
    md = "# Title One\n\n# Title Two\n\n# Title Three"
    result = normalize_headings(md)
    h1_count = result.count("\n# ") + (1 if result.startswith("# ") else 0)
    assert h1_count == 1, f"Expected 1 H1, got {h1_count}"


@pytest.mark.unit
def test_fix_table_alignment_adds_separator():
    md = "| A | B |\n| 1 | 2 |"
    result = fix_table_alignment(md)
    assert "---" in result


@pytest.mark.unit
def test_fix_table_alignment_preserves_valid_table():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = fix_table_alignment(md)
    assert result == md


@pytest.mark.unit
def test_ensure_trailing_newline():
    assert ensure_trailing_newline("text") == "text\n"
    assert ensure_trailing_newline("text\n") == "text\n"
    assert ensure_trailing_newline("text\n\n") == "text\n"


@pytest.mark.unit
def test_postprocess_adds_frontmatter(tmp_path):
    result = ConverterResult(
        markdown="# Hello\n\nWorld",
        converter_used="test",
        metadata={"pages": 3},
    )
    source = tmp_path / "test.pdf"
    md = postprocess(result, source, add_frontmatter=True)
    assert md.startswith("---\n")
    assert 'source: "test.pdf"' in md
    assert 'converter: "test"' in md
    assert "pages: 3" in md


@pytest.mark.unit
def test_postprocess_no_frontmatter(tmp_path):
    result = ConverterResult(markdown="# Hello", converter_used="test")
    source = tmp_path / "doc.pdf"
    md = postprocess(result, source, add_frontmatter=False)
    assert not md.startswith("---")
    assert "# Hello" in md


@pytest.mark.unit
def test_postprocess_ends_with_newline(tmp_path):
    result = ConverterResult(markdown="content", converter_used="test")
    source = tmp_path / "doc.pdf"
    md = postprocess(result, source, add_frontmatter=False)
    assert md.endswith("\n")


# ─── Q-1: Quality scoring ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_quality_high(tmp_path):
    """Rich, structured, warning-free document scores high."""
    from drop2md.postprocess import score_quality

    md = "# Title\n\n## Section\n\n" + ("word " * 450)
    result = ConverterResult(markdown=md, converter_used="marker")
    assert score_quality(md, result) == "high"


@pytest.mark.unit
def test_quality_medium_few_words_with_headings(tmp_path):
    """Moderate word count with at least one heading scores medium."""
    from drop2md.postprocess import score_quality

    md = "# Title\n\n" + ("word " * 150)
    result = ConverterResult(markdown=md, converter_used="marker")
    assert score_quality(md, result) == "medium"


@pytest.mark.unit
def test_quality_low_sparse(tmp_path):
    """Very few words → low quality."""
    from drop2md.postprocess import score_quality

    md = "Just a few words."
    result = ConverterResult(markdown=md, converter_used="pdfplumber")
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_low_scanned_warning(tmp_path):
    """Scanned PDF warning → always low quality regardless of word count."""
    from drop2md.postprocess import score_quality

    md = "# Doc\n\n" + ("word " * 500)
    result = ConverterResult(
        markdown=md,
        converter_used="pdfplumber",
        warnings=["Scanned PDF detected — text extraction may be incomplete."],
    )
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_low_many_warnings(tmp_path):
    """Three or more warnings → always low quality."""
    from drop2md.postprocess import score_quality

    md = "# Doc\n\n## Section\n\n" + ("word " * 500)
    result = ConverterResult(
        markdown=md,
        converter_used="marker",
        warnings=["warn1", "warn2", "warn3"],
    )
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_quality_written_to_frontmatter(tmp_path):
    """postprocess() includes quality: field in YAML frontmatter."""
    md = "# Title\n\n## Section\n\n" + ("word " * 450)
    result = ConverterResult(markdown=md, converter_used="marker")
    source = tmp_path / "doc.pdf"
    out = postprocess(result, source, add_frontmatter=True)
    assert "quality:" in out
    assert "quality: high" in out or "quality: medium" in out or "quality: low" in out


@pytest.mark.unit
def test_quality_not_in_frontmatter_when_disabled(tmp_path):
    """When add_frontmatter=False, quality is not computed or emitted."""
    result = ConverterResult(markdown="# Doc\n\ntext", converter_used="test")
    source = tmp_path / "doc.pdf"
    out = postprocess(result, source, add_frontmatter=False)
    assert "quality:" not in out


@pytest.mark.unit
def test_score_quality_low_fallthrough():
    """score_quality returns 'low' when 100-399 words, no headings/images, 1-2 warnings."""
    from drop2md.postprocess import score_quality

    # 150 words, no headings, no image refs, 2 non-scanned warnings
    md = "word " * 150
    result = ConverterResult(
        markdown=md,
        converter_used="pdfplumber",
        warnings=["minor issue one", "minor issue two"],
    )
    assert score_quality(md, result) == "low"


@pytest.mark.unit
def test_build_frontmatter_includes_warnings():
    """build_frontmatter writes warnings: block when result.warnings is non-empty."""
    from pathlib import Path

    from drop2md.postprocess import build_frontmatter

    result = ConverterResult(
        markdown="# Doc",
        converter_used="marker",
        warnings=["Scanned PDF detected", "Low confidence OCR"],
    )
    fm = build_frontmatter(Path("report.pdf"), result)
    assert "warnings:" in fm
    assert '"Scanned PDF detected"' in fm
    assert '"Low confidence OCR"' in fm


# ── Deterministic polish: fix_hyphen_line_breaks ──────────────────────────────


@pytest.mark.unit
def test_fix_hyphen_line_breaks_rejoins_lowercase():
    """Hyphen-broken word across a newline is rejoined when second fragment is lowercase."""
    assert fix_hyphen_line_breaks("docu-\nment") == "docu-ment"


@pytest.mark.unit
def test_fix_hyphen_line_breaks_multi():
    """Multiple broken words in the same text are all fixed."""
    text = "state-\nof-\nthe art"
    result = fix_hyphen_line_breaks(text)
    assert "\n" not in result.split("art")[0]


@pytest.mark.unit
def test_fix_hyphen_line_breaks_preserves_uppercase():
    """Second fragment starting with uppercase is left unchanged (abbreviation / proper noun)."""
    assert fix_hyphen_line_breaks("EU-\nUS trade") == "EU-\nUS trade"


@pytest.mark.unit
def test_fix_hyphen_line_breaks_preserves_regular_newlines():
    """Normal line breaks (no preceding hyphen) are not touched."""
    text = "line one\nline two"
    assert fix_hyphen_line_breaks(text) == text


# ── Deterministic polish: fix_sentence_spacing ───────────────────────────────


@pytest.mark.unit
def test_fix_sentence_spacing_inserts_space_after_period():
    """Missing space after full stop followed by capital letter is inserted."""
    assert fix_sentence_spacing("sentence.Next word") == "sentence. Next word"


@pytest.mark.unit
def test_fix_sentence_spacing_inserts_space_after_exclamation():
    """Missing space after exclamation mark followed by capital letter is inserted."""
    assert fix_sentence_spacing("done!Start again") == "done! Start again"


@pytest.mark.unit
def test_fix_sentence_spacing_skips_short_word_abbreviations():
    """Words shorter than 3 chars before punctuation are not touched (e.g. Dr., Fig.)."""
    # "Dr" is only 2 chars before the dot — should not insert space
    text = "Dr.Smith is here"
    assert fix_sentence_spacing(text) == text


@pytest.mark.unit
def test_fix_sentence_spacing_skips_urls():
    """Lines containing :// (URLs) are not modified."""
    text = "See https://example.com/Doc for details"
    assert fix_sentence_spacing(text) == text


@pytest.mark.unit
def test_fix_sentence_spacing_skips_code_fence():
    """Content inside triple-backtick fences is not modified."""
    text = "```\nend.Start\n```"
    assert fix_sentence_spacing(text) == text


@pytest.mark.unit
def test_fix_sentence_spacing_already_correct():
    """Text with correct spacing is returned unchanged."""
    text = "First sentence. Second sentence."
    assert fix_sentence_spacing(text) == text


# ── Deterministic polish: fix_repeated_words ─────────────────────────────────


@pytest.mark.unit
def test_fix_repeated_words_removes_duplicate():
    """Consecutive duplicate words (3+ chars) are collapsed to one."""
    assert fix_repeated_words("the the book") == "the book"


@pytest.mark.unit
def test_fix_repeated_words_case_insensitive():
    """Case variation still triggers deduplication."""
    assert fix_repeated_words("The the answer") == "The answer"


@pytest.mark.unit
def test_fix_repeated_words_preserves_short_words():
    """Two-char words are not deduplicated (too risky for legitimate use)."""
    assert fix_repeated_words("ha ha laugh") == "ha ha laugh"


@pytest.mark.unit
def test_fix_repeated_words_three_copies():
    """Three copies of a word collapse to one."""
    assert fix_repeated_words("very very very good") == "very good"


@pytest.mark.unit
def test_fix_repeated_words_no_false_positive():
    """Distinct 3+ char words next to each other are not affected."""
    text = "big red apple"
    assert fix_repeated_words(text) == text


# ── postprocess applies all polish steps ─────────────────────────────────────


@pytest.mark.unit
def test_postprocess_applies_deterministic_polish(tmp_path):
    """postprocess() applies all three deterministic polish steps."""
    raw = "A para-\ngraph with the the same word.Next sentence.\n"
    result = ConverterResult(markdown=raw, converter_used="pdfplumber")
    source = tmp_path / "doc.pdf"
    out = postprocess(result, source, add_frontmatter=False)
    assert "para-\n" not in out  # hyphen rejoined
    assert "the the" not in out  # duplicate removed
    assert "word. Next" in out or "word.Next" not in out  # space inserted
