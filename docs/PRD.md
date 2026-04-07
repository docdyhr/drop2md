# Product Requirements Document: drop2md

**Version:** 2.0
**Date:** 2026-04-07
**Author:** Thomas Juul Dyhr
**Replaces:** PRD v1.0 (2026-04-04)

---

## Problem Statement

Knowledge workers and developers regularly receive documents in PDF, Word,
PowerPoint, Excel, HTML, and EPUB formats. AI assistants — Claude Desktop,
Claude Code, Obsidian AI, RAG pipelines — work best with clean GFM markdown.
The gap between what you receive and what your AI tool can consume is constant
friction.

Manual conversion (open app → export → clean up → move file) interrupts flow.
But the deeper problem is not friction — it is information loss. When a
converter silently drops charts, diagrams, formulas, and visual tables, the
downstream LLM works with an incomplete picture and produces incomplete results.

No existing tool addresses both sides simultaneously:

- **Tooling side:** Most converters are CLI tools with no macOS integration.
  None have a Finder Quick Action. None run as a launchd daemon. None integrate
  with Claude Desktop as an MCP server.
- **Quality side:** Even the best converters treat images as decoration.
  Charts are saved as PNGs with no data extraction. Diagrams are saved as PNGs
  with no structure extraction. Mathematical formulas are unsupported entirely.

drop2md's purpose: close both gaps. Native macOS integration for frictionless
access. AI-enhanced visual intelligence for complete, LLM-ready output.

---

## Strategic Context

drop2md is not competing with enterprise document processing services (Reducto,
LlamaParse, Unstructured). Those tools target large-scale cloud pipelines with
enterprise pricing. drop2md targets individual developers and knowledge workers
who:

- Work primarily on macOS with LLM tools (Claude, Obsidian, Claude Code)
- Care about privacy (local-first processing)
- Value integration with macOS workflows (Finder, launchd, Apple Shortcuts,
  Hazel, Keyboard Maestro)
- Measure success by the quality of markdown they feed to their AI tools

The competitive moat: the intersection of macOS-native UX and LLM-optimized
output. No other tool delivers both.

---

## User Personas

### Persona A — Developer (Thomas)

Works with Claude Code heavily. Primary documents: API docs, research PDFs,
technical specifications, academic papers. Expects YAML frontmatter, images
extracted with meaningful alt-text, tables intact, code blocks preserved.
Comfortable editing config.toml. Runs on M-series MacBook Pro.

Uses the **watcher daemon** for automated processing of files from scripts and
downloads. Uses the **CLI** for one-off batch conversions.

**Critical need:** When a technical paper has a system architecture diagram,
he needs Mermaid code or structured prose — not a PNG labeled "Figure 3."

### Persona B — Knowledge Worker (Maya)

Drops meeting notes (DOCX), slide decks (PPTX), and reports (PDF) from email
and Slack into a folder. Expects markdown to appear in her Obsidian vault
automatically. Does not edit config files.

Uses the **Quick Action** for ad-hoc conversions of individual files.
Uses the **watcher** for automatic processing of files she saves to her drop
folder.

**Critical need:** When a PDF report has a bar chart showing quarterly sales,
she needs the trend and key numbers in text — not a PNG she must open manually
when she later queries her Obsidian vault.

### Persona C — AI Power User (Nico)

Builds personal automation workflows. Uses Claude Desktop via MCP to convert
documents during conversations. Uses Apple Shortcuts and Hazel for document
automation. Cares about output metadata (frontmatter, quality score) because
he pipes markdown into RAG pipelines and vector stores.

Uses the **MCP server** as the primary conversion surface inside Claude.
Uses the **watcher** as the automation backbone for his Hazel rules.

**Critical need:** Reliable quality signal per conversion — the
`quality: high|medium|low` frontmatter field — so his pipeline can route
low-quality conversions for manual review.

---

## Four-Tier Workflow Architecture

drop2md provides four complementary access methods. These are not overlapping
alternatives — they serve distinct jobs:

| Tier | Method | Trigger | Best for |
|---|---|---|---|
| **Automation** | Folder watcher (launchd) | File lands in drop folder | Scripts, Hazel, scanners, programmatic file arrival |
| **Interactive** | Finder Quick Action | Right-click → drop2mark | Ad-hoc conversion, email attachments, one-off decisions |
| **On-demand** | CLI (`drop2md convert`) | Terminal command | Batch conversion, scripting, CI pipelines |
| **Conversational** | MCP server | Claude Desktop prompt | "Convert this PDF" inside a Claude conversation |

**Design principle:** The watcher and Quick Action are not redundant. The
watcher is for files that arrive without a human in the loop. The Quick Action
is for files where a human explicitly decides to convert now. Both are
first-class features.

---

## Feature Requirements

### P0 — Core Conversion (Complete in v0.2.0)

- [x] PDF → GFM (Marker → Docling → PyMuPDF4LLM → pdfplumber fallback chain)
- [x] DOCX/PPTX/XLSX → GFM (MarkItDown + Pandoc fallback)
- [x] HTML → GFM (html2text + Pandoc fallback)
- [x] EPUB → GFM (Pandoc, with image extraction to `images/`)
- [x] PNG/JPG/GIF/WebP/TIFF → GFM (pytesseract OCR + optional AI caption)
- [x] Atomic file writes (`.tmp` → rename pattern, zero partial files)
- [x] YAML frontmatter (source, converted, converter, pages, warnings)
- [x] GFM normalization (heading normalization, table alignment, blank line collapse)
- [x] TOML config with env var overrides
- [x] Rotating log file + stderr fallback

### P0 — macOS Integration (Complete in v0.2.0)

- [x] Folder watcher: FSEventsObserver, 1-second debounce, startup backlog processing
- [x] launchd daemon: KeepAlive, SIGTERM handling, observer auto-restart
- [x] Finder Quick Action: right-click → in-place conversion → macOS notification
- [x] MCP server: `convert_document`, `list_converted`, `get_output_file`,
      `watch_status` tools; `drop2md://output/{filename}` resource
- [x] `drop2md install-service` / `uninstall-service`
- [x] `drop2md install-quick-action` / `uninstall-quick-action`
- [x] `drop2md install-mcp` / `uninstall-mcp`
- [x] `drop2md status` with live refresh and process resource monitoring
- [x] `drop2md check` full setup validation

### P0 — AI Enhancement (Complete in v0.2.0)

- [x] Multi-provider protocol: Ollama, Claude, OpenAI-compatible, HuggingFace
- [x] Image captioning (one-sentence alt-text for extracted images)
- [x] Table validation and GFM repair

### P1 — Visual Intelligence (Target: v0.3)

#### Visual Enhancement Pipeline (VEP)

- [ ] **VEP-1: Visual element classifier** — classify each extracted image as
      `chart | diagram | formula | table-image | screenshot | photo`
- [ ] **VEP-2: Chart description handler** — extract chart type, axes, trend,
      and key data points into a prose paragraph + optional structured comment
- [ ] **VEP-3: Diagram-to-Mermaid handler** — generate Mermaid code for
      flowcharts, sequence diagrams, ER diagrams; prose fallback if the model
      cannot produce valid Mermaid
- [ ] **VEP-4: Formula-to-LaTeX handler** — convert mathematical expressions
      to `$$...$$` blocks
- [ ] **VEP-5: Table-image-to-GFM handler** — recover tables rendered as
      images into GFM pipe tables
- [ ] **VEP-6: Screenshot handler** — descriptive prose paragraph of visible
      UI, content, and purpose
- [ ] **`[visual]` config section** — independent toggle per handler;
      `diagram_to_mermaid` and `formula_to_latex` off by default (opt-in,
      not all renderers support these syntaxes)

#### Office image extraction

- [ ] **DOCX/PPTX embedded image extraction** via `python-docx` / `python-pptx`
      before the MarkItDown conversion pass; extracted images fed into VEP
- [ ] **pdfplumber tier image pass** — when the pdfplumber fallback runs and
      PyMuPDF is available as a library, run image extraction to prevent total
      image loss at the fallback tier

### P1 — Quality and Robustness (Target: v0.4)

- [ ] **Conversion quality scoring** — `quality: high|medium|low` in YAML
      frontmatter; scoring factors: heading density, table count, image ref
      count, word count ratio, warning count
- [x] **Scanned document detection** — page character density check before the
      tier chain; Marker and Docling skipped for image-only PDFs; warning added
      to result (v0.4)
- [ ] **Multi-page progress reporting** — CLI and watcher logs emit converter
      tier selected, page N of M (where available), elapsed time for documents
      > 10 pages
- [ ] **Page-level partial recovery** — mix Marker and pdfplumber output per
      page rather than falling back the whole document on a single page failure
- [x] **RTF and ODT support** via the Pandoc fallback path (v0.4)

### P2 — Distribution and Onboarding (Target: v1.0)

- [ ] `drop2md setup` interactive wizard (config creation, path selection,
      AI provider test, Quick Action and service install)
- [ ] Homebrew formula and tap (`brew install docdyhr/tap/drop2md`)
- [ ] GitHub Release prebuilt binary (PyInstaller or Briefcase) for users
      without Python
- [ ] `output.vault_dir` config option for Obsidian vault integration
- [ ] Test coverage ≥ 85%, mypy strict clean
- [ ] Signed and notarized macOS package (Gatekeeper compliance)

### P3 — Platform Extensibility (Target: v2.0)

- [ ] Plugin system (pip entry points for third-party converters and enhancers)
- [ ] Webhook and event system (HTTP, Apple Shortcuts URL scheme)
- [ ] Conversion history database (SQLite) and dashboard (FastAPI + htmx)
- [ ] Password-protected PDF handling (ghostscript)
- [ ] Docker image for Linux/server deployment

---

## Non-Goals

- Not a cloud service. Local-first. Cloud AI providers are optional and
  explicitly configured by the user.
- Not a document editor. Source files are never modified.
- Not an enterprise pipeline. No multi-user, access control, audit logs, SLA.
- Not a Pandoc replacement. Pandoc is a used component.
- Does not handle documents requiring authentication or login.
- Not competing with Reducto/LlamaParse on forms, checkboxes, or structured
  data extraction from enterprise documents.

---

## Visual Intelligence Architecture (v0.3 target)

### Current pipeline (v0.2)

```
[ConverterResult with extracted images]
         ↓
enhance(result, config)
         ↓
_inject_image_captions()   ← one prompt per image, no classification
_enhance_tables()          ← GFM table repair
         ↓
[final ConverterResult]
```

### Target pipeline (v0.3)

```
[ConverterResult with extracted images]
         ↓
enhance(result, config)
         ↓
classify_visual_elements()  ← batch classify all images (single API call)
         ↓
per-class dispatch:
  chart        → describe_chart()        → prose + structured comment
  diagram      → diagram_to_mermaid()    → Mermaid code or prose fallback
  formula      → formula_to_latex()      → $$...$$ block
  table-image  → table_image_to_gfm()    → GFM pipe table
  screenshot   → describe_screenshot()   → prose paragraph
  photo        → describe_image()        ← existing (unchanged)
         ↓
_enhance_tables()           ← existing (unchanged)
         ↓
[final ConverterResult]
```

The classifier makes a single batch API call listing all extracted images to
minimise round-trips. All handlers use the existing `AIProvider` protocol —
no new provider code required.

### New `[visual]` config section

```toml
[visual]
enabled = true
classify = true
chart_description = true
diagram_to_mermaid = false    # opt-in: not all renderers support Mermaid
formula_to_latex = false      # opt-in: not all renderers support LaTeX
table_image_to_gfm = true
screenshot_description = true
```

---

## Technical Requirements

| Requirement | Specification |
|---|---|
| Python version | 3.11+ |
| macOS version | 13 Ventura+ |
| Architecture | Apple Silicon primary (MPS for Marker) + Intel fallback |
| Output format | GitHub Flavored Markdown, UTF-8 |
| Max conversion time (core) | < 30s for PDF < 50 pages, no AI enhancement |
| Max conversion time (v0.3 VEP) | < 90s for PDF < 50 pages with full visual intelligence |
| Image output | PNG in `images/` subdirectory relative to output markdown |
| Config format | TOML (stdlib tomllib) |
| Logging | Rotating file (5MB, 3 backups) + stderr fallback |
| Test coverage | ≥ 77% at v0.2 (current), ≥ 85% at v1.0 |
| Packaging | `pyproject.toml`, `pip install -e .` |
| Atomic writes | All output via `.tmp` → rename |
| Privacy | No network calls without explicit user configuration |

---

## Dependency Architecture

```
[core]          watchdog, typer, html2text, python-magic, httpx, pdfplumber, mcp, psutil
[pdf-ml]        marker-pdf, docling                  (~2GB, optional)
[pdf-light]     pymupdf4llm                          (lightweight, optional)
[office]        markitdown[docx]                     (DOCX/PPTX/XLSX, optional)
[office-images] python-docx, python-pptx             (v0.3 embedded image extraction, optional)
[ocr]           pytesseract, Pillow                  (image OCR, optional)
[claude]        anthropic>=0.40.0                    (Claude AI enhancement, optional)
[openai]        openai>=1.50.0                       (OpenAI/Gemini/HF enhancement, optional)
[dev]           ruff, mypy, bandit, pre-commit, pip-audit
[test]          pytest + coverage + mock + timeout plugins
[all]           everything above
```

---

## Success Metrics

### Conversion quality

1. 20-page born-digital PDF with tables → clean GFM in < 20 seconds,
   `quality: high` in frontmatter.
2. All GFM tables render correctly in GitHub, Obsidian, and Claude Desktop.
3. Images saved to `output/images/` with correct relative refs in markdown.
4. PDF with a bar chart (AI enhancement enabled, v0.3) → output contains a
   prose paragraph describing chart type, trend, and at least 2 data points.
5. PPTX with 3 embedded slide images (v0.3) → output contains 3 image refs
   with AI-generated descriptions.

### Reliability

6. Service survives Mac restart (launchd KeepAlive confirmed).
7. Zero files left in partial state after abrupt termination (atomic writes).
8. FSEvents observer auto-restarts after unexpected death.
9. AI enhancement failure never blocks conversion — output is always written.

### Developer experience

10. `drop2md check` exits 0 on a correctly configured system.
11. CI passes on every commit (ruff, mypy, pytest, bandit, pip-audit).
12. YAML frontmatter present in every converted file.
13. `drop2md status` shows correct service state, process resources, and
    recent conversions without error.
