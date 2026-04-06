"""Unit tests for enhance_providers — all SDK calls mocked."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from drop2md.enhance_providers import (
    ClaudeProvider,
    OllamaProvider,
    OpenAICompatProvider,
    make_provider,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _cfg(provider: str = "ollama", api_key: str = "") -> MagicMock:
    cfg = MagicMock()
    cfg.ollama.provider = provider
    cfg.ollama.api_key = api_key
    cfg.ollama.base_url = "http://localhost:11434"
    cfg.ollama.model = "qwen3.5:latest"
    cfg.ollama.timeout_seconds = 5
    cfg.openai.model = "gpt-4o-mini"
    cfg.openai.base_url = "https://api.openai.com/v1"
    cfg.openai.timeout_seconds = 5
    cfg.claude.model = "claude-haiku-4-5-20251001"
    cfg.claude.timeout_seconds = 5
    return cfg


def _mock_httpx_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"response": text}
    resp.raise_for_status.return_value = None
    return resp


# ─── OllamaProvider ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_ollama_provider_text_prompt():
    provider = OllamaProvider("http://localhost:11434", "test-model", timeout=5)
    with patch("httpx.post", return_value=_mock_httpx_response("Hello from Ollama")) as mock_post:
        result = provider.generate("Say hello")
    assert result == "Hello from Ollama"
    call_kwargs = mock_post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
    assert payload["model"] == "test-model"
    assert payload["options"] == {"think": False}


@pytest.mark.unit
def test_ollama_provider_sends_image(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG")  # minimal fake PNG bytes
    provider = OllamaProvider("http://localhost:11434", "test-model", timeout=5)
    with patch("httpx.post", return_value=_mock_httpx_response("A chart")) as mock_post:
        result = provider.generate("Describe this", image_path=img)
    assert result == "A chart"
    payload = mock_post.call_args.kwargs["json"]
    assert "images" in payload
    assert len(payload["images"]) == 1


@pytest.mark.unit
def test_ollama_provider_skips_missing_image(tmp_path):
    provider = OllamaProvider("http://localhost:11434", "test-model", timeout=5)
    missing = tmp_path / "ghost.png"
    with patch("httpx.post", return_value=_mock_httpx_response("ok")) as mock_post:
        provider.generate("Describe this", image_path=missing)
    payload = mock_post.call_args.kwargs["json"]
    assert "images" not in payload


# ─── OpenAICompatProvider ────────────────────────────────────────────────────

@pytest.mark.unit
def test_openai_provider_text_prompt():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello from OpenAI"
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    provider = OpenAICompatProvider("gpt-4o-mini", "https://api.openai.com/v1", "", timeout=5)
    with patch.dict(sys.modules, {"openai": mock_openai}):
        result = provider.generate("Say hello")

    assert result == "Hello from OpenAI"
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.unit
def test_openai_provider_sends_image(tmp_path):
    img = tmp_path / "chart.png"
    img.write_bytes(b"\x89PNG")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "A chart"
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    provider = OpenAICompatProvider("gpt-4o-mini", "https://api.openai.com/v1", "", timeout=5)
    with patch.dict(sys.modules, {"openai": mock_openai}):
        result = provider.generate("Describe", image_path=img)

    assert result == "A chart"
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    # Content should be a list containing text + image_url blocks
    assert isinstance(messages[0]["content"], list)
    content_types = {block["type"] for block in messages[0]["content"]}
    assert "image_url" in content_types


@pytest.mark.unit
def test_openai_provider_import_error():
    provider = OpenAICompatProvider("gpt-4o-mini", "https://api.openai.com/v1", "", timeout=5)
    with patch("builtins.__import__", side_effect=ImportError("No module named 'openai'")), \
         pytest.raises(ImportError, match="openai package"):
        provider.generate("Hello")


# ─── ClaudeProvider ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_claude_provider_text_prompt():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "Hello from Claude"
    mock_message.content = [mock_block]
    mock_client.messages.create.return_value = mock_message

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    provider = ClaudeProvider("claude-haiku-4-5-20251001", "", timeout=5)
    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        result = provider.generate("Say hello")

    assert result == "Hello from Claude"
    mock_client.messages.create.assert_called_once()


@pytest.mark.unit
def test_claude_provider_sends_image(tmp_path):
    img = tmp_path / "chart.png"
    img.write_bytes(b"\x89PNG")

    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "A chart"
    mock_message.content = [mock_block]
    mock_client.messages.create.return_value = mock_message

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    provider = ClaudeProvider("claude-haiku-4-5-20251001", "", timeout=5)
    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        result = provider.generate("Describe", image_path=img)

    assert result == "A chart"
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    content = messages[0]["content"]
    content_types = {block["type"] for block in content}
    assert "image" in content_types


@pytest.mark.unit
def test_claude_provider_import_error():
    provider = ClaudeProvider("claude-haiku-4-5-20251001", "", timeout=5)
    with patch("builtins.__import__", side_effect=ImportError("No module named 'anthropic'")), \
         pytest.raises(ImportError, match="anthropic package"):
        provider.generate("Hello")


# ─── make_provider factory ───────────────────────────────────────────────────

@pytest.mark.unit
def test_make_provider_returns_ollama():
    from drop2md.enhance_providers import OllamaProvider
    provider = make_provider(_cfg(provider="ollama"))
    assert isinstance(provider, OllamaProvider)


@pytest.mark.unit
def test_make_provider_returns_claude():
    from drop2md.enhance_providers import ClaudeProvider
    provider = make_provider(_cfg(provider="claude"))
    assert isinstance(provider, ClaudeProvider)


@pytest.mark.unit
def test_make_provider_returns_openai():
    from drop2md.enhance_providers import OpenAICompatProvider
    provider = make_provider(_cfg(provider="openai"))
    assert isinstance(provider, OpenAICompatProvider)


@pytest.mark.unit
def test_make_provider_returns_openai_for_hf():
    from drop2md.enhance_providers import OpenAICompatProvider
    provider = make_provider(_cfg(provider="hf"))
    assert isinstance(provider, OpenAICompatProvider)


@pytest.mark.unit
def test_make_provider_raises_on_unknown():
    with pytest.raises(ValueError, match="Unknown enhance provider"):
        make_provider(_cfg(provider="groq"))
