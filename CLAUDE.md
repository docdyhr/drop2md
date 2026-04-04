# CLAUDE.md — drop2md Developer Guide

## Project Overview

`drop2md` is a macOS document-to-markdown converter with folder watching.
It converts PDF, DOCX, PPTX, XLSX, HTML, EPUB, and image files to clean GFM markdown,
optimized for use with Claude Desktop, Claude Code, and other LLM tools.

## Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # or: direnv allow (reads .envrc)

# Install with all dev + test extras
pip install -e ".[dev,test]"

# Install with full ML support (large download ~2GB)
pip install -e ".[dev,test,pdf-ml,office,ocr]"

# Configure
cp config.toml.example config.toml
# Edit config.toml to set watch_dir and output_dir
```

## Docs

| File | Contents |
|---|---|
| `docs/testing.md` | Full testing reference — pytest, CLI, MCP inspector, watcher, AI providers |
| `docs/mcp_integration.md` | Claude Desktop setup and MCP tool reference |
| `docs/PRD.md` | Product requirements |

## Common Commands

```bash
# One-shot conversion
drop2md convert path/to/file.pdf
drop2md convert path/to/file.pdf --output ~/Desktop/output/

# Start watcher (foreground)
drop2md watch
drop2md watch --config path/to/config.toml

# Install as macOS background service (launchd)
drop2md install-service
drop2md uninstall-service
drop2md status

# Run tests
pytest
pytest -m unit          # fast unit tests only
pytest -m "not slow"    # skip slow tests
pytest -k test_pdf      # run tests matching pattern

# Lint and type-check
ruff check src/ tests/
ruff format src/ tests/
mypy src/

# Security audit
bandit -r src/
pip-audit
```

## Package Structure

```
src/drop2md/
├── __init__.py         # version, public API
├── cli.py              # typer CLI entry point
├── config.py           # TOML config loader
├── watcher.py          # FSEvents folder watcher
├── dispatcher.py       # MIME-type routing
├── postprocess.py      # GFM cleanup + frontmatter
├── ollama_enhance.py   # optional Ollama AI enhancement
├── converters/
│   ├── __init__.py     # ConverterResult, BaseConverter
│   ├── pdf.py          # tiered PDF conversion
│   ├── office.py       # DOCX/PPTX/XLSX
│   ├── html.py         # HTML
│   ├── epub.py         # EPUB via pandoc
│   ├── image.py        # PNG/JPG OCR
│   └── legacy_pdf.py   # pdfplumber fallback
└── utils/
    ├── image_extractor.py
    ├── gfm.py
    ├── fs.py
    └── logging.py
```

## Adding a New Converter

1. Create `src/drop2md/converters/myformat.py`
2. Subclass `BaseConverter` from `converters/__init__.py`
3. Implement `convert(path, config) -> ConverterResult` and `is_available() -> bool`
4. Register in `dispatcher.py` MIME_MAP
5. Add tests in `tests/unit/` and `tests/integration/`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DROP2MD_CONFIG` | `./config.toml` | Path to config file |
| `DROP2MD_WATCH_DIR` | from config | Override watch directory |
| `DROP2MD_OUTPUT_DIR` | from config | Override output directory |
| `DROP2MD_OLLAMA_ENABLED` | `false` | Enable Ollama enhancement |
| `DROP2MD_LOG_LEVEL` | `INFO` | Log verbosity |

## Dependency Extras

| Extra | Contents | When to use |
|---|---|---|
| `[core]` | watchdog, typer, html2text, httpx | Always (default) |
| `[pdf-ml]` | marker-pdf, docling | Best PDF quality, needs ~2GB download |
| `[pdf-light]` | pymupdf4llm | Lightweight PDF alternative |
| `[office]` | markitdown | DOCX/PPTX/XLSX support |
| `[ocr]` | pytesseract, Pillow | Image/scanned PDF OCR |
| `[dev]` | ruff, mypy, bandit, pre-commit | Development |
| `[test]` | pytest + plugins | Testing |
| `[all]` | everything | Full install |
