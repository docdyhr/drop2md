# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- GitHub Actions CI (pytest + ruff, Python 3.11/3.12/3.13)
- Legacy `pdf_to_markdown.py` preserved as standalone script
