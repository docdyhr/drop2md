"""AI provider abstraction for drop2md enhancement pipeline.

Supports Ollama (local) and OpenAI-compatible APIs (OpenAI, Gemini, HuggingFace).
All providers share the same AIProvider protocol.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, Protocol
from urllib.parse import urlparse

if TYPE_CHECKING:
    from drop2md.config import Config

log = logging.getLogger(__name__)

# The host of the `[openai] base_url` default. A Gemini or Hugging Face key
# must never be sent there.
_OPENAI_API_HOST = "api.openai.com"


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

        # Prepend /no_think if not already present — required for qwen3/deepseek-r1
        # reasoning models to suppress chain-of-thought that can take minutes.
        # The options.think=False flag alone is insufficient for some model versions.
        effective_prompt = (
            prompt if prompt.startswith("/no_think") else f"/no_think {prompt}"
        )

        payload: dict = {
            "model": self._model,
            "prompt": effective_prompt,
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
        return str(resp.json().get("response", "")).strip()


class OpenAICompatProvider:
    """OpenAI-compatible chat completions API (covers OpenAI, HuggingFace Inference Router).

    Requires ``openai`` package (``pip install drop2md[openai]``).
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        timeout: int,
        reasoning_effort: str = "",
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._reasoning_effort = reasoning_effort

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
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{img_type};base64,{img_b64}"},
                        },
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": self._model, "messages": messages}
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        response = client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()


def make_provider(config: Config) -> AIProvider:
    """Factory: create the correct provider based on ``config.ollama.provider``.

    Supported values: ``"ollama"`` (default), ``"openai"``, ``"gemini"``, ``"hf"``.
    ``"hf"`` uses OpenAICompatProvider with ``config.openai.base_url`` pointing at
    the HuggingFace Inference Router.
    """
    import os

    provider_name: str = getattr(config.ollama, "provider", "ollama")
    api_key: str = getattr(config.ollama, "api_key", "")

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=config.ollama.base_url,
            model=config.ollama.model,
            timeout=config.ollama.timeout_seconds,
        )

    if provider_name == "claude":
        _raise_provider_error(
            "The 'claude' provider was removed (it required an Anthropic API key). "
            "Use 'ollama', 'openai', 'gemini' or 'hf'."
        )

    if provider_name == "openai":
        # Fall back to OPENAI_API_KEY, then GEMINI_API_KEY (for Google endpoints).
        # The Gemini key is used only when base_url is not OpenAI's own API.
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key and not _is_openai_endpoint(config.openai.base_url):
            resolved_key = os.environ.get("GEMINI_API_KEY", "")
        return OpenAICompatProvider(
            model=config.openai.model,
            base_url=config.openai.base_url,
            api_key=resolved_key,
            timeout=config.openai.timeout_seconds,
            reasoning_effort=getattr(config.openai, "reasoning_effort", ""),
        )

    if provider_name == "gemini":
        # Dedicated Gemini provider — reads GEMINI_API_KEY automatically
        resolved_key = _own_endpoint_key(
            config, provider_name, "GEMINI_API_KEY", api_key
        )
        return OpenAICompatProvider(
            model=config.openai.model,
            base_url=config.openai.base_url,
            api_key=resolved_key,
            timeout=config.openai.timeout_seconds,
        )

    if provider_name == "hf":
        # HuggingFace uses HF_TOKEN; the openai SDK won't read it automatically
        resolved_key = _own_endpoint_key(config, provider_name, "HF_TOKEN", api_key)
        return OpenAICompatProvider(
            model=config.openai.model,
            base_url=config.openai.base_url,
            api_key=resolved_key,
            timeout=config.openai.timeout_seconds,
        )

    _raise_provider_error(
        f"Unknown enhance provider: {provider_name!r}. "
        "Valid values: 'ollama', 'openai', 'gemini', 'hf'."
    )


def _is_openai_endpoint(base_url: str) -> bool:
    """Return True when *base_url* points at OpenAI's own API host."""
    return (urlparse(str(base_url)).hostname or "") == _OPENAI_API_HOST


def _own_endpoint_key(
    config: Config, provider_name: str, key_var: str, api_key: str
) -> str:
    """Resolve the gemini or hf key, refusing any setup that would send a key elsewhere.

    Both providers read ``[openai] base_url``, whose default is OpenAI's API, so
    without an override their key would go to OpenAI. And with no key at all,
    ``OpenAICompatProvider`` passes ``api_key=None``, which makes the openai SDK
    read ``OPENAI_API_KEY`` and send that to Google or Hugging Face.
    """
    import os

    if _is_openai_endpoint(config.openai.base_url):
        _raise_provider_error(
            f"provider {provider_name!r} needs [openai] base_url set to its own "
            f"OpenAI-compatible endpoint; it points at {_OPENAI_API_HOST}, so the "
            f"{key_var} key would be sent to OpenAI."
        )
    resolved_key = api_key or os.environ.get(key_var, "")
    if not resolved_key:
        _raise_provider_error(
            f"provider {provider_name!r} has no API key: set {key_var} (or [ollama] "
            "api_key / DROP2MD_ENHANCE_API_KEY). Without one the openai client "
            "would send OPENAI_API_KEY instead."
        )
    return resolved_key


_warned_provider_errors: set[str] = set()


def _raise_provider_error(message: str) -> NoReturn:
    """Raise ValueError, logging a warning once per message per process.

    Every caller in enhance.py catches exceptions and logs at debug level, so
    without the warning a misconfigured provider silently skips enhancement.
    """
    if message not in _warned_provider_errors:
        _warned_provider_errors.add(message)
        log.warning("AI enhancement disabled: %s", message)
    raise ValueError(message)


def _mime_from_suffix(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix.lower(), "image/png")
