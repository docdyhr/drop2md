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
├── __init__.py         # __version__, author metadata
├── py.typed            # PEP 561 marker
├── cli.py              # typer CLI entry point
├── config.py           # TOML config loader
├── watcher.py          # FSEvents folder watcher
├── dispatcher.py       # MIME-type routing
├── postprocess.py      # GFM cleanup + frontmatter
├── enhance.py          # optional AI enhancement: image captions or VEP, table repair, text polish
├── enhance_providers.py # AI providers: Ollama, OpenAI-compatible (OpenAI, Gemini, HF)
├── ollama_enhance.py   # backward-compat shim: re-exports enhance, describe_image, validate_table
├── mcp_server.py       # MCP server (stdio) for Claude Desktop
├── services/           # Finder Quick Action templates (Info.plist, document.wflow)
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
    ├── logging.py
    └── process_monitor.py
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
| `DROP2MD_OLLAMA_ENABLED` | `false` | Enable AI enhancement (any provider) |
| `DROP2MD_ENHANCE_PROVIDER` | `ollama` | Enhancement provider: `ollama`, `openai`, `gemini` or `hf` |
| `DROP2MD_ENHANCE_API_KEY` | unset | A non-empty value overrides `[ollama] api_key`. If both are empty: `OPENAI_API_KEY` (then `GEMINI_API_KEY`) for `openai`, `GEMINI_API_KEY` for `gemini`, `HF_TOKEN` for `hf`; `ollama` uses no key |
| `DROP2MD_VAULT_DIR` | unset | Override `[output] vault_dir` |
| `DROP2MD_LOG_LEVEL` | `INFO` | Log verbosity |

An override applies only when its variable is set to a non-empty value (`config.py`, `_apply_env_overrides`); an empty one leaves the config value in place.

## Dependency Extras

| Extra | Contents | When to use |
|---|---|---|
| (base, no extra) | watchdog, typer, html2text, python-magic, httpx, pdfplumber, mcp[cli], psutil | Always installed |
| `[pdf-ml]` | marker-pdf, docling | Best PDF quality, needs ~2GB download |
| `[pdf-light]` | pymupdf4llm | Lightweight PDF alternative |
| `[office]` | markitdown[docx] | DOCX. PPTX also needs python-pptx (`[office-images]`); XLSX needs openpyxl and pandas, which no extra declares |
| `[office-images]` | python-docx, python-pptx | Extract embedded images from DOCX/PPTX |
| `[ocr]` | pytesseract, Pillow | Image/scanned PDF OCR |
| `[openai]` | openai | SDK for the `openai`, `gemini` and `hf` enhancement providers |
| `[dev]` | ruff, mypy, pre-commit, bandit, pip-audit | Development |
| `[test]` | pytest + plugins | Testing |
| `[all]` | everything | Full install |

## Vendored Agent Skills (`.claude/skills/`)

The skills in `.claude/skills/` are third-party (github/awesome-copilot; see its README) and stay
byte-identical to upstream: refresh them from upstream, never edit them here. Where a skill
disagrees with this file, this file wins:

- **Report, don't act.** `docs-sync-audit`, `test-gap-audit`, `github-actions-hardening` report in
  chat. Don't write report files into the repo, and don't change workflows, action pins or
  `.github/dependabot.yml` unless asked.
- **PRs and Dependabot.** Never merge, approve, close or enable auto-merge (`gh pr merge --auto`) on
  PRs, and don't post `@dependabot` commands.
- **No installs.** Don't install plugins, MCP toolsets or skills that a skill file links to (for
  example `advanced-security@copilot-plugins`), and don't change agent or editor settings.
- **Tests.** Follow this repo's own test commands and coverage settings above, not a skill's generic
  defaults.
