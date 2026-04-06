# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-04-06

### Added
- `drop2md status` now shows a **Process Resources** table: PID, role (watcher/mcp-server/converter), status, CPU%, RSS, memory%, file descriptors, and uptime for all running drop2md processes
- `drop2md status --watch` (`-w`) for live-refreshing display (like `top`) using `rich.Live`
- `drop2md status --interval` (`-n`) to control refresh rate in seconds (default: 2.0)
- `psutil>=6.0.0` added to core dependencies for cross-platform process introspection
- `src/drop2md/utils/process_monitor.py` — isolated module with `ProcessInfo` dataclass and `sample_processes()` (two-poll CPU sampling, role inference from cmdline, graceful handling of vanished processes)
- `reasoning_effort` support in `OpenAICompatProvider` for o-series and reasoning models (`low`/`medium`/`high`)
- `reasoning_effort` field in `[openai]` config section
- ChatGPT (gpt-5.2) and Gemini example blocks in `config.toml.example`
- Watcher enqueues files already present at startup so they aren't skipped on first run
- 16 new unit tests; total coverage 76.84%

### Fixed
- Watcher registers `SIGTERM` handler for clean shutdown and auto-restarts the FSEvents observer if it dies unexpectedly
- PID parsing in `_get_launchd_pid()` now uses `re.search(r'"PID"\s*=\s*(\d+)', ...)` — the previous `.strip('"PID" = ')` was character-set stripping, not substring removal
- Residual `doc2md` → `drop2md` rename in `config.toml.example` and launchd plist template

## [0.1.0] — 2026-04-04

### Added
- Initial project scaffold with `src/drop2md` package layout
- `ConverterResult` dataclass and `BaseConverter` ABC
- Tiered PDF converter: Marker → Docling → PyMuPDF4LLM → pdfplumber fallback
- Office converter (DOCX/PPTX/XLSX) via MarkItDown + Pandoc fallback
- HTML converter via html2text + Pandoc fallback
- EPUB converter via Pandoc
- Image converter via pytesseract OCR
- Image extractor: saves embedded images to `output/images/`
- GFM postprocessor: YAML frontmatter, heading normalization
- TOML config with tomllib (stdlib)
- `watchdog` FSEventsObserver with 1-second debounce
- Typer CLI: `convert`, `watch`, `install-service`, `status`
- launchd plist template for macOS background service
- Optional Ollama integration for image captioning and table validation
- MCP server for Claude Desktop integration (`install-mcp`, `drop2md-mcp`)
- Multi-provider AI enhancement: Claude (Anthropic), OpenAI/ChatGPT, and HuggingFace Inference Router as alternatives to Ollama
- `enhance_providers.py` with `AIProvider` Protocol, `OllamaProvider`, `OpenAICompatProvider`, `ClaudeProvider`, and `make_provider()` factory
- `[openai]` and `[claude]` config sections with per-provider model and timeout settings
- `provider` and `api_key` fields in `[ollama]` config section
- `DROP2MD_ENHANCE_PROVIDER` and `DROP2MD_ENHANCE_API_KEY` environment variable overrides
- Optional `[claude]` (anthropic>=0.40.0) and `[openai]` (openai>=1.50.0) pip extras
- GitHub Actions CI (pytest + ruff, Python 3.11/3.12/3.13)
- 160 unit tests at 80%+ coverage
- Legacy `pdf_to_markdown.py` preserved as standalone script

### Changed
- Enhancement pipeline routes through `make_provider()` based on `ollama.provider` config field (default: `"ollama"`, backward compatible)

[Unreleased]: https://github.com/docdyhr/drop2md/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/docdyhr/drop2md/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/docdyhr/drop2md/releases/tag/v0.1.0
