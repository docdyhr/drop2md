# Product Requirements Document: drop2md

**Version:** 1.0
**Date:** 2026-04-04
**Author:** Thomas Juul Dyhr

---

## Problem Statement

Knowledge workers and developers regularly receive documents in PDF, Word,
PowerPoint, Excel, HTML, and EPUB formats. AI assistants (Claude Desktop,
Claude Code, Cowork AI) work best with clean plain-text input in GFM markdown.

The manual conversion workflow — open app, export, clean up formatting — is
friction that interrupts flow and degrades input quality. The LLM receives
poorly-structured text instead of semantically rich markdown with tables,
images, and headings preserved.

There is no turnkey macOS solution that:
- Monitors a folder
- Converts any dropped document using best-in-class tools per format
- Preserves tables and images with proper markdown references
- Optionally enriches output using a local LLM (Ollama)
- Runs as a persistent background service

---

## User Personas

**Persona A — Developer (Thomas)**
Uses Claude Code heavily. Drops API docs, research PDFs, and technical specs
into a folder. Expects output in `~/Documents/markdown-output/` with images
extracted, tables intact, and a YAML frontmatter block. Comfortable editing
`config.toml`. Runs on M-series MacBook Pro (Apple Silicon).

**Persona B — Knowledge Worker**
Drops meeting notes (DOCX), slide decks (PPTX), and reports (PDF) into a
Finder folder. Expects markdown output to appear in Obsidian vault
automatically. Needs `install.sh` to handle setup.

---

## MVP Features

### P0 — Must Have
- [x] Watch a drop folder with launchd + watchdog FSEvents
- [x] PDF → GFM conversion (tiered: Marker → Docling → PyMuPDF4LLM → pdfplumber)
- [x] DOCX/PPTX/XLSX → GFM via MarkItDown + Pandoc fallback
- [x] Atomic file writes (prevent partial reads by Claude Desktop)
- [x] launchd plist + `install-service` command

### P1 — Should Have
- [x] HTML → GFM via html2text
- [x] Image extraction → `output/images/` with relative markdown refs
- [x] YAML frontmatter (source, date, converter_used, pages)
- [x] TOML config file (all paths + feature toggles)
- [x] CLI: `convert`, `watch`, `install-service`, `uninstall-service`, `status`
- [x] GitHub Actions CI (pytest + ruff, Python 3.11/3.12/3.13)

### P2 — Nice to Have
- [x] EPUB → GFM via Pandoc
- [x] PNG/JPG OCR via tesseract
- [x] Ollama image captioning (optional, qwen3.5 vision)
- [x] Ollama table validation (optional)
- [x] 1-second debounce for in-progress file writes

### P3 — Future
- [ ] MCP server for Claude Desktop direct triggering
- [ ] Obsidian vault sync (write directly into vault)
- [ ] Web UI dashboard (FastAPI + htmx) with conversion history
- [ ] Password-protected PDF handling (ghostscript)
- [ ] RTF, ODT, CSV support
- [ ] Webhook notifications on successful conversion
- [ ] Docker container for non-Mac deployment

---

## Non-Goals

- Not a cloud service — all processing is local
- Not a document editor
- Does not handle documents requiring login/authentication
- Does not modify source files in the drop folder
- Not a Pandoc replacement (uses Pandoc as a component)

---

## Technical Requirements

| Requirement | Specification |
|---|---|
| Python version | 3.11+ (tomllib stdlib, union types) |
| macOS version | 13 Ventura+ (FSEvents stability) |
| Architecture | Apple Silicon (MPS for Marker) + Intel fallback |
| Output format | GitHub Flavored Markdown (GFM), UTF-8 |
| Max conversion time | < 30s for PDF < 50 pages without Ollama |
| Image output | PNG, saved to `images/` subdirectory |
| Config format | TOML (stdlib tomllib) |
| Logging | Rotating file log (5MB, 3 backups) + stderr |
| Test coverage | ≥ 30% unit at v0.1.0, ≥ 60% at v1.0 |
| Packaging | `pyproject.toml`, installable as `pip install -e .` |

---

## Success Metrics

1. Drop a 20-page PDF with tables → clean GFM output in < 20 seconds
2. Tables in output are valid GFM (render correctly in GitHub, Obsidian, Claude)
3. Images saved to `output/images/` with correct relative refs in markdown
4. Service survives Mac restart (`launchd` KeepAlive)
5. Zero files left in partial state after abrupt termination (atomic writes)
6. CI passes on every commit (ruff, mypy, pytest)
7. YAML frontmatter present in every converted file

---

## Dependency Architecture

```
[core]      watchdog, typer, html2text, python-magic, httpx, pdfplumber
[pdf-ml]    marker-pdf, docling   (optional, ~2GB PyTorch)
[pdf-light] pymupdf4llm           (optional, lightweight)
[office]    markitdown[all]       (optional)
[ocr]       pytesseract, Pillow   (optional)
[dev]       ruff, mypy, bandit, pre-commit, pip-audit
[test]      pytest + coverage plugins
[all]       everything above
```

---

## Architecture Diagram

```
[Drop Folder] ──► watcher.py (FSEventsObserver + 1s debounce)
                       │
                  dispatcher.py  (MIME-type routing via python-magic)
                       │
          ┌────────────┼──────────────────┐
      pdf.py       office.py          image.py
   (tiered)      (MarkItDown)      (pytesseract)
   Marker→                         + Ollama vision
   Docling→
   PyMuPDF4LLM→
   pdfplumber
          └────────────┼──────────────────┘
                  image_extractor.py  (save PNG → output/images/)
                       │
                  postprocess.py  (frontmatter, GFM normalize)
                       │
                 [optional] ollama_enhance.py
                       │
                  fs.atomic_write → output/{filename}.md
```
