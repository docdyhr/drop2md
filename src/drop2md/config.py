"""TOML configuration loader for drop2md.

Reads config.toml (or a path from DROP2MD_CONFIG env var) and returns a
frozen Config dataclass. All path values are expanded via Path.expanduser().
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass
class PathsConfig:
    watch_dir: Path = field(default_factory=lambda: Path("~/Documents/drop-to-md").expanduser())
    output_dir: Path = field(default_factory=lambda: Path("~/Documents/markdown-output").expanduser())


@dataclass
class PdfConfig:
    use_marker: bool = True
    use_docling: bool = True
    marker_device: str = "mps"


@dataclass
class OfficeConfig:
    use_markitdown: bool = True


@dataclass
class OcrConfig:
    enabled: bool = True
    language: str = "eng"


@dataclass
class OllamaConfig:
    enabled: bool = False
    base_url: str = "http://localhost:11434"
    model: str = "qwen3.5:latest"
    timeout_seconds: int = 60
    provider: str = "ollama"   # "ollama" | "claude" | "openai" | "hf"
    api_key: str = ""          # blank → SDK reads env var (ANTHROPIC_API_KEY etc.)


@dataclass
class OpenAIConfig:
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"  # override for HF router
    timeout_seconds: int = 30
    reasoning_effort: str = ""  # "low" | "medium" | "high" — only for reasoning models


@dataclass
class ClaudeConfig:
    model: str = "claude-haiku-4-5-20251001"
    timeout_seconds: int = 30


@dataclass
class OutputConfig:
    add_frontmatter: bool = True
    image_subdir: str = "images"
    preserve_page_markers: bool = False
    overwrite: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = ""


@dataclass
class Config:
    paths: PathsConfig = field(default_factory=PathsConfig)
    pdf: PdfConfig = field(default_factory=PdfConfig)
    office: OfficeConfig = field(default_factory=OfficeConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def ensure_dirs(self) -> None:
        """Create watch_dir and output_dir if they do not exist."""
        self.paths.watch_dir.mkdir(parents=True, exist_ok=True)
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)


def _expand_paths(cfg: Config) -> None:
    cfg.paths.watch_dir = Path(cfg.paths.watch_dir).expanduser()
    cfg.paths.output_dir = Path(cfg.paths.output_dir).expanduser()


def load_config(path: Path | None = None) -> Config:
    """Load config from *path* (defaults to DROP2MD_CONFIG env var or config.toml).

    Missing file → returns default Config.
    """
    if path is None:
        env_path = os.environ.get("DROP2MD_CONFIG")
        path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH

    if not path.exists():
        cfg = Config()
        _apply_env_overrides(cfg)
        return cfg

    with path.open("rb") as f:
        data = tomllib.load(f)

    paths_data = data.get("paths", {})
    cfg = Config(
        paths=PathsConfig(
            watch_dir=Path(paths_data.get("watch_dir", "~/Documents/drop-to-md")),
            output_dir=Path(paths_data.get("output_dir", "~/Documents/markdown-output")),
        ),
        pdf=PdfConfig(**data.get("pdf", {})),
        office=OfficeConfig(**data.get("office", {})),
        ocr=OcrConfig(**data.get("ocr", {})),
        ollama=OllamaConfig(**data.get("ollama", {})),
        openai=OpenAIConfig(**data.get("openai", {})),
        claude=ClaudeConfig(**data.get("claude", {})),
        output=OutputConfig(**data.get("output", {})),
        logging=LoggingConfig(**data.get("logging", {})),
    )
    _expand_paths(cfg)
    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: Config) -> None:
    if val := os.environ.get("DROP2MD_WATCH_DIR"):
        cfg.paths.watch_dir = Path(val).expanduser()
    if val := os.environ.get("DROP2MD_OUTPUT_DIR"):
        cfg.paths.output_dir = Path(val).expanduser()
    if val := os.environ.get("DROP2MD_OLLAMA_ENABLED"):
        cfg.ollama.enabled = val.lower() in {"1", "true", "yes"}
    if val := os.environ.get("DROP2MD_ENHANCE_PROVIDER"):
        cfg.ollama.provider = val
    if val := os.environ.get("DROP2MD_ENHANCE_API_KEY"):
        cfg.ollama.api_key = val
    if val := os.environ.get("DROP2MD_LOG_LEVEL"):
        cfg.logging.level = val.upper()
