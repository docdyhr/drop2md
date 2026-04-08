"""Integration tests for Ollama AI enhancement (requires Ollama running locally).

Run with:
    pytest tests/integration/test_ollama_enhancement.py -v -m ollama

Skipped automatically if Ollama is not reachable at http://localhost:11434.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL = "qwen3-vl:8b"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _ollama_available() -> bool:
    try:
        import httpx

        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _model_available() -> bool:
    try:
        import httpx

        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        tags = r.json().get("models", [])
        return any(MODEL in t.get("name", "") for t in tags)
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not reachable at localhost:11434",
)

requires_model = pytest.mark.skipif(
    not _model_available(),
    reason=f"Model {MODEL!r} not pulled in Ollama",
)


def _make_config(enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.ollama.enabled = enabled
    cfg.ollama.base_url = OLLAMA_BASE_URL
    cfg.ollama.model = MODEL
    cfg.ollama.timeout_seconds = 300
    cfg.ollama.provider = "ollama"
    cfg.ollama.api_key = ""
    return cfg


# ── Provider-level tests ─────────────────────────────────────────────────────


@pytest.mark.ollama
@requires_ollama
@requires_model
def test_ollama_text_prompt_returns_nonempty():
    """Model responds to a plain text prompt."""
    from drop2md.enhance_providers import OllamaProvider

    provider = OllamaProvider(OLLAMA_BASE_URL, MODEL, timeout=300)
    result = provider.generate("/no_think Say the word PONG and nothing else.")
    assert result.strip(), "Expected non-empty response"


@pytest.mark.ollama
@pytest.mark.timeout(360)
@requires_ollama
@requires_model
def test_ollama_image_captioning(sample_png: Path):
    """Model returns a non-empty caption for a real PNG fixture."""
    from drop2md.enhance_providers import OllamaProvider

    provider = OllamaProvider(OLLAMA_BASE_URL, MODEL, timeout=300)
    prompt = (
        "/no_think Describe this image from a document in one concise sentence "
        "suitable for use as Markdown alt-text. Be specific and factual."
    )
    result = provider.generate(prompt, image_path=sample_png)
    assert result.strip(), "Expected non-empty image caption"
    assert len(result) > 10, "Caption too short to be meaningful"


# ── enhance() pipeline tests ─────────────────────────────────────────────────


@pytest.mark.ollama
@pytest.mark.timeout(360)
@requires_ollama
@requires_model
def test_enhance_injects_image_alt_text(sample_png: Path, tmp_path: Path):
    """enhance() replaces empty alt-text with a model-generated caption."""
    from drop2md.converters import ConverterResult
    from drop2md.enhance import enhance

    # Simulate a converter result with a bare image ref (empty alt-text)
    img_dest = tmp_path / "images" / sample_png.name
    img_dest.parent.mkdir()
    img_dest.write_bytes(sample_png.read_bytes())

    bare_ref = f"![](./{img_dest.parent.name}/{img_dest.name})"
    result = ConverterResult(
        markdown=f"# Test\n\n{bare_ref}\n",
        images=[img_dest],
        converter_used="test",
    )

    enhanced = enhance(result, _make_config())
    assert "![" in enhanced.markdown
    # Alt-text should now be non-empty
    assert "![](." not in enhanced.markdown, "Bare image ref was not replaced"


@pytest.mark.ollama
@pytest.mark.timeout(360)
@requires_ollama
@requires_model
def test_enhance_fixes_table(tmp_path: Path):
    """enhance() passes tables through the model and returns valid GFM."""
    from drop2md.converters import ConverterResult
    from drop2md.enhance import enhance

    broken = "| Col A | Col B |\n|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    result = ConverterResult(
        markdown=f"# Data\n\n{broken}",
        converter_used="test",
    )

    enhanced = enhance(result, _make_config())
    assert "|" in enhanced.markdown
    assert "Col A" in enhanced.markdown


@pytest.mark.ollama
@requires_ollama
@requires_model
def test_enhance_disabled_is_noop():
    """enhance() returns the original result unchanged when ollama.enabled=False."""
    from drop2md.converters import ConverterResult
    from drop2md.enhance import enhance

    original_md = "# Hello\n\nSome text.\n"
    result = ConverterResult(markdown=original_md, converter_used="test")

    enhanced = enhance(result, _make_config(enabled=False))
    assert enhanced.markdown == original_md
