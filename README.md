# doc2md

[![CI](https://github.com/docdyhr/doc2md/actions/workflows/ci.yml/badge.svg)](https://github.com/docdyhr/doc2md/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**doc2md** is a macOS document-to-markdown converter that watches a drop folder
and automatically converts documents to clean GFM markdown — optimized for
Claude Desktop, Claude Code, Cowork, and any LLM-based workflow.

Drop a PDF, Word doc, PowerPoint, spreadsheet, or web page into the watch folder
and get a clean `.md` file with preserved tables, extracted images, and YAML
frontmatter in seconds.

## Features

- **Multi-format support**: PDF, DOCX, PPTX, XLSX, HTML, EPUB, PNG/JPG
- **Best-in-class converters**: Marker (PDF), MarkItDown (Office), html2text (HTML)
- **Tiered PDF conversion**: Marker → Docling → PyMuPDF4LLM → pdfplumber fallback
- **Table preservation**: GFM pipe tables, maintained reading order
- **Image extraction**: Embedded images saved separately, referenced with relative paths
- **YAML frontmatter**: source, date, converter used — great for LLM context
- **macOS background service**: launchd integration, survives restarts
- **Optional Ollama**: local LLM for image captions and table validation
- **Apple Silicon**: Marker uses Apple MPS for fast inference on M-series Macs

## Quick Start

### Requirements

- macOS 13 Ventura+ (Apple Silicon or Intel)
- Python 3.11+
- [Homebrew](https://brew.sh) (for pandoc, tesseract)

```bash
# Install system dependencies
brew install pandoc tesseract

# Install doc2md (core + office support)
pip install -e ".[office]"

# Configure
cp config.toml.example config.toml
# Edit config.toml: set watch_dir and output_dir

# Start watching (foreground)
doc2md watch

# Or install as macOS background service
doc2md install-service
```

### Install Full ML Support (Best PDF Quality)

```bash
# Requires ~2GB download (PyTorch + Marker)
pip install -e ".[pdf-ml,office,ocr]"
```

### One-Shot Conversion

```bash
doc2md convert report.pdf
doc2md convert presentation.pptx --output ~/Desktop/
doc2md convert *.docx --output ~/Documents/markdown/
```

## Configuration

Copy `config.toml.example` to `config.toml` and edit:

```toml
[paths]
watch_dir  = "~/Documents/drop-to-md"
output_dir = "~/Documents/markdown-output"

[pdf]
use_marker  = true
marker_device = "mps"   # Apple Silicon

[ollama]
enabled  = false          # set true to enable AI enhancement
provider = "ollama"       # "ollama" | "claude" | "openai" | "hf"
model    = "qwen3.5:latest"
```

See [`config.toml.example`](config.toml.example) for all options.

## macOS Service

```bash
# Install and start background service
doc2md install-service

# Check status
doc2md status

# Remove service
doc2md uninstall-service

# Logs
tail -f ~/Library/Logs/doc2md/doc2md.log
```

## Claude Desktop Integration

Claude Desktop can read PDFs directly with full vision support (tables, charts,
images all understood). Converted markdown is still preferred because:

- Works with Claude Code (CLI) which cannot display PDFs
- Reduces token usage — pre-extracted text costs less than PDF vision processing
- Works universally across all LLM tools (Obsidian, Cowork, any RAG pipeline)
- Extracted images are stored as separate files Claude can view on demand

## Output Format

Each converted file includes a YAML frontmatter block:

```markdown
---
source: "report.pdf"
converted: "2026-04-04T14:23:01"
converter: "marker"
pages: 12
---

# Report Title

## Section 1

| Column A | Column B |
|---|---|
| value 1 | value 2 |

![Figure 1](./images/report_1_0.png)
```

## Supported Formats

| Format | Converter | Notes |
|---|---|---|
| PDF | Marker / Docling / pdfplumber | Tiered fallback |
| DOCX | MarkItDown / Pandoc | Tables, headings preserved |
| PPTX | MarkItDown | Slide text + notes |
| XLSX | MarkItDown | Multiple sheets as tables |
| HTML | html2text / Pandoc | Links preserved |
| EPUB | Pandoc | Chapter structure |
| PNG/JPG | pytesseract + AI caption | OCR + optional AI description |

## Optional AI Enhancement

When `[ollama] enabled = true`, doc2md runs an optional post-processing pass:

- **Image captions**: Embedded images get AI-generated alt-text
- **Table validation**: Broken GFM tables are auto-corrected

Four providers are supported. Set `provider` in your `config.toml`:

```toml
[ollama]
enabled  = true
provider = "ollama"   # "ollama" | "claude" | "openai" | "hf"
model    = "qwen3.5:latest"
```

| Provider | Extra install | API key env var | Notes |
|---|---|---|---|
| `ollama` | — (default) | — | Free, local, requires Ollama running |
| `claude` | `pip install doc2md[claude]` | `ANTHROPIC_API_KEY` | Claude Haiku by default |
| `openai` | `pip install doc2md[openai]` | `OPENAI_API_KEY` | GPT-4o-mini by default |
| `hf` | `pip install doc2md[openai]` | `HF_TOKEN` | HuggingFace Inference Router |

API keys are resolved in order: `api_key` field in config → `DOC2MD_ENHANCE_API_KEY` env var → provider-native env var.

All providers fall back gracefully — a missing key or offline service never blocks conversion.

## Development

See [CLAUDE.md](CLAUDE.md) for the full developer guide.

```bash
pip install -e ".[dev,test]"
pytest
ruff check src/ tests/
```

## License

MIT — see [LICENSE](LICENSE)
