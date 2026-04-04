"""AI provider abstraction for drop2md enhancement pipeline.

Supports Ollama (local), OpenAI-compatible APIs (OpenAI, HuggingFace), and Anthropic Claude.
All providers share the same AIProvider protocol.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)


class AIProvider(Protocol):
    """Minimal interface all enhancement providers must implement."""

    def generate(self, prompt: str, image_path: Path | None = None) -> str:
        """Send a prompt (optionally with an image) and return the text response."""
        ...


class OllamaProvider:
    """Calls Ollama's native /api/generate endpoint via httpx."""

    def __init__(self, base_url: str, model: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str, image_path: Path | None = None) -> str:
        import httpx

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"think": False},
        }
        if image_path and image_path.exists():
            img_b64 = base64.b64encode(image_path.read_bytes()).decode()
            payload["images"] = [img_b64]

        resp = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


class OpenAICompatProvider:
    """OpenAI-compatible chat completions API (covers OpenAI, HuggingFace Inference Router).

    Requires ``openai`` package (``pip install drop2md[openai]``).
    """

    def __init__(self, model: str, base_url: str, api_key: str, timeout: int) -> None:
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout

    def generate(self, prompt: str, image_path: Path | None = None) -> str:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAI/HuggingFace providers. "
                "Install it with: pip install drop2md[openai]"
            ) from exc

        client = openai.OpenAI(
            api_key=self._api_key or None,
            base_url=self._base_url,
            timeout=self._timeout,
        )

        messages: list[dict] = []
        if image_path and image_path.exists():
            img_b64 = base64.b64encode(image_path.read_bytes()).decode()
            img_type = _mime_from_suffix(image_path.suffix)
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{img_type};base64,{img_b64}"},
                    },
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return (response.choices[0].message.content or "").strip()


class ClaudeProvider:
    """Anthropic Claude API provider with native base64 image vision.

    Requires ``anthropic`` package (``pip install drop2md[claude]``).
    """

    def __init__(self, model: str, api_key: str, timeout: int) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def generate(self, prompt: str, image_path: Path | None = None) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for the Claude provider. "
                "Install it with: pip install drop2md[claude]"
            ) from exc

        client = anthropic.Anthropic(
            api_key=self._api_key or None,
            timeout=self._timeout,
        )

        content: list[dict] = []
        if image_path and image_path.exists():
            img_b64 = base64.b64encode(image_path.read_bytes()).decode()
            img_type = _mime_from_suffix(image_path.suffix)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img_type,
                    "data": img_b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        message = client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        block = message.content[0]
        return (block.text if hasattr(block, "text") else "").strip()


def make_provider(config: object) -> AIProvider:
    """Factory: create the correct provider based on ``config.ollama.provider``.

    Supported values: ``"ollama"`` (default), ``"claude"``, ``"openai"``, ``"hf"``.
    ``"hf"`` uses OpenAICompatProvider with ``config.openai.base_url`` pointing at
    the HuggingFace Inference Router.
    """
    import os

    provider_name: str = getattr(config.ollama, "provider", "ollama")  # type: ignore[union-attr]
    api_key: str = getattr(config.ollama, "api_key", "")  # type: ignore[union-attr]

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=config.ollama.base_url,  # type: ignore[union-attr]
            model=config.ollama.model,  # type: ignore[union-attr]
            timeout=config.ollama.timeout_seconds,  # type: ignore[union-attr]
        )

    if provider_name == "claude":
        # Fall back to ANTHROPIC_API_KEY; passing None lets the SDK read it
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        return ClaudeProvider(
            model=config.claude.model,  # type: ignore[union-attr]
            api_key=resolved_key,
            timeout=config.claude.timeout_seconds,  # type: ignore[union-attr]
        )

    if provider_name == "openai":
        # Fall back to OPENAI_API_KEY; passing None lets the SDK read it
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        return OpenAICompatProvider(
            model=config.openai.model,  # type: ignore[union-attr]
            base_url=config.openai.base_url,  # type: ignore[union-attr]
            api_key=resolved_key,
            timeout=config.openai.timeout_seconds,  # type: ignore[union-attr]
        )

    if provider_name == "hf":
        # HuggingFace uses HF_TOKEN; the openai SDK won't read it automatically
        resolved_key = api_key or os.environ.get("HF_TOKEN", "")
        return OpenAICompatProvider(
            model=config.openai.model,  # type: ignore[union-attr]
            base_url=config.openai.base_url,  # type: ignore[union-attr]
            api_key=resolved_key,
            timeout=config.openai.timeout_seconds,  # type: ignore[union-attr]
        )

    raise ValueError(
        f"Unknown enhance provider: {provider_name!r}. "
        "Valid values: 'ollama', 'claude', 'openai', 'hf'."
    )


def _mime_from_suffix(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix.lower(), "image/png")
