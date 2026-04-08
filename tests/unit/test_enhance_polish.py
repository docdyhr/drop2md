"""Unit tests for the AI-assisted text polish feature (_polish_text)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConverterResult
from drop2md.enhance import _polish_text, enhance


def _cfg(*, polish_text: bool = True, ollama_enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.ollama.enabled = ollama_enabled
    cfg.ollama.provider = "ollama"
    cfg.ollama.model = "llava-llama3:8b"
    cfg.ollama.base_url = "http://localhost:11434"
    cfg.ollama.timeout_seconds = 5
    cfg.ollama.api_key = ""
    cfg.ollama.polish_text = polish_text
    cfg.ollama.validate_tables = False  # keep tables untouched for isolation
    cfg.visual.enabled = False
    return cfg


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"response": text}
    resp.raise_for_status.return_value = None
    return resp


@pytest.mark.unit
def test_polish_text_corrects_obvious_errors():
    """_polish_text accepts a correctly-sized AI response and updates markdown."""
    original = "This docurnent has an error."
    corrected = "This document has an error."
    result = ConverterResult(markdown=original, converter_used="pdfplumber")

    with patch("httpx.post", return_value=_mock_response(corrected)):
        out = _polish_text(result, _cfg())

    assert out.markdown == corrected


@pytest.mark.unit
def test_polish_text_falls_back_on_oversized_response():
    """_polish_text rejects AI response that is more than 130% of original length."""
    original = "Short text here."
    bloated = original + " " + ("extra words " * 100)
    result = ConverterResult(markdown=original, converter_used="pdfplumber")

    with patch("httpx.post", return_value=_mock_response(bloated)):
        out = _polish_text(result, _cfg())

    assert out.markdown == original


@pytest.mark.unit
def test_polish_text_falls_back_on_undersized_response():
    """_polish_text rejects AI response that is less than 75% of original length."""
    original = "A sufficiently long paragraph with many words to trigger the safety check properly."
    tiny = "Too short."
    result = ConverterResult(markdown=original, converter_used="pdfplumber")

    with patch("httpx.post", return_value=_mock_response(tiny)):
        out = _polish_text(result, _cfg())

    assert out.markdown == original


@pytest.mark.unit
def test_polish_text_falls_back_on_provider_error():
    """_polish_text returns the original result when the AI provider raises."""
    import httpx

    original = "Text with an error."
    result = ConverterResult(markdown=original, converter_used="pdfplumber")

    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        out = _polish_text(result, _cfg())

    assert out.markdown == original


@pytest.mark.unit
def test_polish_text_skips_tables():
    """Paragraphs that are GFM tables are never sent to the AI provider."""
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = ConverterResult(markdown=table, converter_used="pdfplumber")

    with patch("httpx.post") as mock_post:
        _polish_text(result, _cfg())

    mock_post.assert_not_called()


@pytest.mark.unit
def test_polish_text_skips_code_blocks():
    """Paragraphs inside triple-backtick fences are never sent to the AI provider."""
    code = "```python\nprint('hello')\n```"
    result = ConverterResult(markdown=code, converter_used="pdfplumber")

    with patch("httpx.post") as mock_post:
        _polish_text(result, _cfg())

    mock_post.assert_not_called()


@pytest.mark.unit
def test_polish_text_skips_headings():
    """Heading paragraphs are never sent to the AI provider."""
    heading = "# My Document Title"
    result = ConverterResult(markdown=heading, converter_used="pdfplumber")

    with patch("httpx.post") as mock_post:
        _polish_text(result, _cfg())

    mock_post.assert_not_called()


@pytest.mark.unit
def test_polish_text_preserves_metadata():
    """_polish_text preserves all ConverterResult fields beyond markdown."""
    original = "Some text."
    corrected = "Some text."
    result = ConverterResult(
        markdown=original,
        converter_used="marker",
        metadata={"pages": 5},
        warnings=["Low quality"],
    )

    with patch("httpx.post", return_value=_mock_response(corrected)):
        out = _polish_text(result, _cfg())

    assert out.converter_used == "marker"
    assert out.metadata == {"pages": 5}
    assert out.warnings == ["Low quality"]


@pytest.mark.unit
def test_enhance_calls_polish_when_enabled():
    """enhance() calls _polish_text when ollama.polish_text=True."""
    md = "A docurnent with an error."
    corrected = "A document with an error."
    result = ConverterResult(markdown=md, converter_used="pdfplumber")

    with patch(
        "drop2md.enhance._polish_text",
        return_value=ConverterResult(
            markdown=corrected,
            converter_used="pdfplumber",
        ),
    ) as mock_polish:
        out = enhance(result, _cfg(polish_text=True))

    mock_polish.assert_called_once()
    assert out.markdown == corrected


@pytest.mark.unit
def test_enhance_skips_polish_when_disabled():
    """enhance() does not call _polish_text when ollama.polish_text=False."""
    md = "Text here."
    result = ConverterResult(markdown=md, converter_used="pdfplumber")

    with patch("drop2md.enhance._polish_text") as mock_polish:
        enhance(result, _cfg(polish_text=False))

    mock_polish.assert_not_called()


@pytest.mark.unit
def test_enhance_polish_exception_is_swallowed():
    """enhance() catches _polish_text exceptions and returns the original markdown."""
    md = "Text here."
    result = ConverterResult(markdown=md, converter_used="pdfplumber")

    with patch("drop2md.enhance._polish_text", side_effect=RuntimeError("boom")):
        out = enhance(result, _cfg(polish_text=True))

    assert out.markdown == md


@pytest.mark.unit
def test_polish_text_mixed_content(tmp_path):
    """Prose paragraphs are polished; tables and headings are preserved verbatim."""
    md = "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nThis is prose with docurnent error.\n"
    result = ConverterResult(markdown=md, converter_used="pdfplumber")

    call_count = 0

    def _side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        prompt = kwargs.get("json", {}).get("prompt", "")
        if "docurnent" in prompt:
            return _mock_response("This is prose with document error.")
        return _mock_response(prompt.split("Text:\n")[-1].strip())

    with patch("httpx.post", side_effect=_side_effect):
        out = _polish_text(result, _cfg())

    # Heading and table untouched, prose corrected
    assert "# Title" in out.markdown
    assert "| A | B |" in out.markdown
    assert call_count == 1  # only the prose paragraph was sent
