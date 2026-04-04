"""Unit tests for the enhance pipeline — all provider calls mocked via OllamaProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from doc2md.converters import ConverterResult
from doc2md.enhance import describe_image, enhance, validate_table


def _cfg(enabled: bool = True, timeout: int = 5, provider: str = "ollama") -> MagicMock:
    cfg = MagicMock()
    cfg.ollama.enabled = enabled
    cfg.ollama.provider = provider
    cfg.ollama.model = "test-model"
    cfg.ollama.base_url = "http://localhost:11434"
    cfg.ollama.timeout_seconds = timeout
    cfg.ollama.api_key = ""
    cfg.openai.model = "gpt-4o-mini"
    cfg.openai.base_url = "https://api.openai.com/v1"
    cfg.openai.timeout_seconds = timeout
    cfg.claude.model = "claude-haiku-4-5-20251001"
    cfg.claude.timeout_seconds = timeout
    return cfg


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"response": text}
    resp.raise_for_status.return_value = None
    return resp


# ─── validate_table ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_validate_table_returns_fixed_table():
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    fixed = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    with patch("httpx.post", return_value=_mock_response(fixed)):
        result = validate_table(table, _cfg())
    assert result == fixed


@pytest.mark.unit
def test_validate_table_falls_back_when_no_pipe_in_response():
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    with patch("httpx.post", return_value=_mock_response("Sorry, I cannot help.")):
        result = validate_table(table, _cfg())
    assert result == table


@pytest.mark.unit
def test_validate_table_falls_back_on_timeout():
    import httpx
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        result = validate_table(table, _cfg())
    assert result == table


@pytest.mark.unit
def test_validate_table_falls_back_on_connection_error():
    import httpx
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = validate_table(table, _cfg())
    assert result == table


# ─── describe_image ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_describe_image_returns_alt_text(tmp_path):
    img = tmp_path / "chart.png"
    img.write_bytes(b"fake-png")
    with patch("httpx.post", return_value=_mock_response("A bar chart showing Q1 sales.")):
        result = describe_image(img, _cfg())
    assert result == "A bar chart showing Q1 sales."


@pytest.mark.unit
def test_describe_image_returns_empty_on_error(tmp_path):
    import httpx
    img = tmp_path / "chart.png"
    img.write_bytes(b"fake-png")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = describe_image(img, _cfg())
    assert result == ""


# ─── enhance ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_enhance_disabled_config_returns_unchanged():
    result = ConverterResult(markdown="| A |\n|---|\n| 1 |", converter_used="test")
    with patch("httpx.post") as mock_post:
        out = enhance(result, _cfg(enabled=False))
    mock_post.assert_not_called()
    assert out.markdown == result.markdown


@pytest.mark.unit
def test_enhance_calls_table_validation_when_tables_present():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = ConverterResult(markdown=md, converter_used="test")
    fixed = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    with patch("httpx.post", return_value=_mock_response(fixed)):
        out = enhance(result, _cfg())
    assert "|" in out.markdown


@pytest.mark.unit
def test_enhance_skips_table_validation_when_no_tables():
    result = ConverterResult(markdown="# Just prose\n\nNo tables here.", converter_used="test")
    with patch("httpx.post") as mock_post:
        out = enhance(result, _cfg())
    mock_post.assert_not_called()
    assert out.markdown == result.markdown


@pytest.mark.unit
def test_enhance_preserves_metadata():
    result = ConverterResult(
        markdown="| A |\n|---|\n| 1 |",
        converter_used="marker",
        metadata={"pages": 5},
        warnings=["some warning"],
    )
    with patch("httpx.post", return_value=_mock_response("| A |\n|---|\n| 1 |")):
        out = enhance(result, _cfg())
    assert out.converter_used == "marker"
    assert out.metadata == {"pages": 5}
    assert out.warnings == ["some warning"]
