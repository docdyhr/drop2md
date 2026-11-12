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

# Domains each vendor serves its API from. A provider's key is never sent to
# another vendor's domains; `[openai] base_url` defaults to OpenAI's.
_VENDOR_DOMAINS: dict[str, tuple[str, ...]] = {
    "openai": ("openai.com",),
    "gemini": ("googleapis.com",),
    "hf": ("huggingface.co", "huggingface.cloud"),
}
_VENDOR_NAMES = {"openai": "OpenAI", "gemini": "Google", "hf": "Hugging Face"}
# Each vendor's own key variable, and the OpenAI-compatible endpoint to suggest.
_VENDOR_KEY_VARS = {"gemini": "GEMINI_API_KEY", "hf": "HF_TOKEN"}
_PROVIDER_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "hf": "https://router.huggingface.co/v1",
}


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
        # At Google's or Hugging Face's endpoint that vendor's own variable
        # (GEMINI_API_KEY / HF_TOKEN) comes before OPENAI_API_KEY; elsewhere only
        # OPENAI_API_KEY is read.
        if problem := _endpoint_refusal(config.openai.base_url, provider_name):
            _raise_provider_error(problem)
        resolved_key = api_key
        own_var = _VENDOR_KEY_VARS.get(_endpoint_vendor(config.openai.base_url))
        if not resolved_key and own_var:
            resolved_key = os.environ.get(own_var, "")
        if not resolved_key:
            resolved_key = os.environ.get("OPENAI_API_KEY", "")
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


def _endpoint_scheme(base_url: str) -> str:
    """Return the lower-cased URL scheme of *base_url* ('' when it has none)."""
    try:
        return urlparse(str(base_url).strip()).scheme.lower()
    except ValueError:
        return ""


def _endpoint_host(base_url: str) -> str:
    """Return the normalised host of an http(s) *base_url*, or '' when it has none."""
    if _endpoint_scheme(base_url) not in ("http", "https"):
        return ""  # no scheme, protocol-relative, or one the openai client cannot use
    try:
        host = urlparse(str(base_url).strip()).hostname or ""
    except ValueError:  # e.g. an unbalanced IPv6 bracket
        return ""
    try:
        # Folds fullwidth and ideographic dots to "." (a trailing one included),
        # so the trailing dot is stripped afterwards.
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    return host.rstrip(".").lower()


def _endpoint_vendor(base_url: str) -> str:
    """Return the vendor whose domains serve *base_url* ('openai', 'gemini', 'hf'), else ''."""
    host = _endpoint_host(base_url)
    for vendor, domains in _VENDOR_DOMAINS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return vendor
    return ""


def _endpoint_refusal(base_url: str, provider_name: str) -> str:
    """Return why *base_url* must not receive *provider_name*'s key, or '' if it may.

    Every provider refuses a base_url with no http(s) host and plain http:// to a
    known vendor's domain (the key would travel unencrypted). gemini and hf also
    refuse another vendor's domain. The message carries no key and no base_url.
    """
    own_url = _PROVIDER_BASE_URLS.get(provider_name, "")
    example = f", e.g. {own_url}" if own_url else ""
    if not _endpoint_host(base_url):
        return (
            f"provider {provider_name!r} needs [openai] base_url set to the full URL "
            f"(with https://) of its OpenAI-compatible endpoint{example}"
        )
    vendor = _endpoint_vendor(base_url)
    if vendor and _endpoint_scheme(base_url) != "https":
        return (
            f"provider {provider_name!r}: [openai] base_url points at a "
            f"{_VENDOR_NAMES[vendor]} host over plain http://, which would send the "
            "key unencrypted; use https://"
        )
    if provider_name in _VENDOR_KEY_VARS and vendor and vendor != provider_name:
        return (
            f"provider {provider_name!r} needs [openai] base_url set to its own "
            f"OpenAI-compatible endpoint, but its host belongs to "
            f"{_VENDOR_NAMES[vendor]}, so {_VENDOR_KEY_VARS[provider_name]} would be "
            f"sent to {_VENDOR_NAMES[vendor]}. Use e.g. {own_url}"
        )
    return ""


def _own_endpoint_key(
    config: Config, provider_name: str, key_var: str, api_key: str
) -> str:
    """Resolve the gemini or hf key, refusing a base_url on another vendor's domains.

    Both providers read ``[openai] base_url``, whose default is OpenAI's API, so
    without an override their key would go to OpenAI, and a base_url left over
    from the other provider would send it to that vendor. A self-hosted or proxy
    endpoint (no known vendor domain) is allowed; only these four domains are
    recognised, so another hosted API counts as self-hosted. See
    `_endpoint_refusal` for the endpoint rules. With no key at all,
    ``OpenAICompatProvider`` would pass ``api_key=None``, which makes the openai
    SDK read ``OPENAI_API_KEY`` and send that instead, so a missing key is refused.
    """
    import os

    if problem := _endpoint_refusal(config.openai.base_url, provider_name):
        _raise_provider_error(problem)
    resolved_key = api_key or os.environ.get(key_var, "")
    if not resolved_key:
        _raise_provider_error(
            f"provider {provider_name!r} has no API key: set {key_var} (or [ollama] "
            "api_key). Without one the openai client would send OPENAI_API_KEY instead."
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
