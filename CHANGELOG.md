# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-04

### Added
- Initial project scaffold with `src/doc2md` package layout
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
- MCP server for Claude Desktop integration (`install-mcp`, `doc2md-mcp`)
- Multi-provider AI enhancement: Claude (Anthropic), OpenAI/ChatGPT, and HuggingFace Inference Router as alternatives to Ollama
- `enhance_providers.py` with `AIProvider` Protocol, `OllamaProvider`, `OpenAICompatProvider`, `ClaudeProvider`, and `make_provider()` factory
- `[openai]` and `[claude]` config sections with per-provider model and timeout settings
- `provider` and `api_key` fields in `[ollama]` config section
- `DOC2MD_ENHANCE_PROVIDER` and `DOC2MD_ENHANCE_API_KEY` environment variable overrides
- Optional `[claude]` (anthropic>=0.40.0) and `[openai]` (openai>=1.50.0) pip extras
- GitHub Actions CI (pytest + ruff, Python 3.11/3.12/3.13)
- 160 unit tests at 80%+ coverage
- Legacy `pdf_to_markdown.py` preserved as standalone script

### Changed
- Enhancement pipeline routes through `make_provider()` based on `ollama.provider` config field (default: `"ollama"`, backward compatible)

[0.1.0]: https://github.com/docdyhr/doc2md/releases/tag/v0.1.0
