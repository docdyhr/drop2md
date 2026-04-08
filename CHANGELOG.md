# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **D-1/D-3/D-6 macOS distribution pipeline** — PyInstaller onedir binary (pdf-light + office + ocr; no torch), GitHub Actions release workflow triggered on `v*` tags, code-signed with Developer ID Application + notarized via `xcrun notarytool`, stapled .dmg published as GitHub Release asset. Homebrew formula added to `docdyhr/homebrew-tap` (`brew install docdyhr/tap/drop2md`). SHA-256 placeholder in formula updated automatically from CI job summary after each release.

## [0.5.0] — 2026-04-07

### Added

- **Markdown polish — deterministic + AI-assisted text correction** — two-tier post-processing pipeline for common PDF extraction artifacts:
  - **Deterministic (always-on)**: `fix_hyphen_line_breaks` rejoins words split across lines by PDF column layout (`docu-\nment` → `docu-ment`); `fix_sentence_spacing` inserts missing spaces after sentence-ending punctuation (`text.Next` → `text. Next`); `fix_repeated_words` removes adjacent duplicate words caused by extraction boundary artifacts (`the the` → `the`). Applied in `postprocess()` after heading normalisation, zero latency, no config needed.
  - **AI-assisted (opt-in)**: `_polish_text()` in `enhance.py` splits markdown on paragraph boundaries, skips structural blocks (tables, headings, code fences, image refs, URLs), and sends each prose paragraph to the configured AI provider with a strict prompt that forbids rephrasing. Safety length check (0.75–1.30× ratio) rejects responses that deviate too far from the original. Enable with `polish_text = true` in `[ollama]` config.
  - 27 new unit tests: 14 in `test_postprocess.py` (per-function and end-to-end deterministic), 13 in new `test_enhance_polish.py` (AI fallbacks, structural paragraph skipping, metadata preservation, wire-up).
- **D-2 `drop2md setup` interactive wizard** — guided first-run experience: prompts for watch/output/vault directories, AI provider (none/ollama/claude/openai/gemini), model and API key, optional VEP enable; offers to install the launchd service and Finder Quick Action; runs an Ollama connection test if that provider is chosen. Writes a complete `config.toml` without any manual TOML editing.
- **D-4 Obsidian vault integration** — `output.vault_dir` in `[output]` config section (also settable via `DROP2MD_VAULT_DIR` env var). When set, every converted markdown file is atomic-written to `vault_dir/<filename>.md` in addition to the standard output directory. Supported in the watcher, CLI `convert`, and MCP `convert_document`.
- **D-5 Coverage ≥ 85% and mypy strict clean** — 59 new unit tests covering VEP branch paths (diagram/formula/screenshot/photo fallbacks, unreferenced-image append with extra, `_enhance_tables` dispatch), `ProcessingLock` FileExistsError race condition, `atomic_write` failure cleanup, `score_quality` low fallthrough, `build_frontmatter` with warnings, `OpenAICompatProvider` reasoning_effort branch, `make_provider` gemini path, `mcp_server.main()`, `list_converted` with non-existent output dir, enhancement exception handling in MCP server, and `drop2md setup` wizard flows (8 scenarios). Total: 334 unit tests, 85.1% line coverage.
- **Ruff and mypy clean** — fixed pre-existing `B005` PID parsing in `check` (now uses regex), `E741` ambiguous var, `I001` import sort issues in source and test files, `SIM117` nested `with` statements, `[arg-type]`/`[typeddict-item]` mypy ignores for Anthropic SDK and Rich Group, `[arg-type]` cast for watchdog bytes|str event path.

## [0.4.0] — 2026-04-07

### Added

- **Q-1 Conversion quality scoring** — `postprocess.py` computes a `quality: high | medium | low` score and writes it to YAML frontmatter. Scoring is purely structural (no AI): word count, heading density, image ref count, warning count, and scanned-PDF flag. Boundaries: `high` ≥ 400 words + ≥ 2 headings + 0 warnings; `low` if scanned, ≥ 3 warnings, or < 100 words; `medium` otherwise.
- **Q-2 Scanned PDF detection** — `TieredPdfConverter` now samples the first 3 pages with pdfplumber before running any converter; if total character count is < 20 the PDF is treated as scanned. Marker and Docling (which produce garbage on image-only pages) are skipped automatically. A `"Scanned PDF detected"` warning is appended to the `ConverterResult` so downstream tools can surface the quality downgrade.
- **Q-5 RTF and ODF support** — `dispatcher.py` now routes `.rtf`, `.odt`, `.odp`, `.ods` files (and their MIME types) to `OfficeConverter`, which hands them to the Pandoc fallback. No new dependencies required.
- **Q-3 Progress reporting** — CLI `convert` command now prints elapsed time and page count for documents > 10 pages; conversion warnings are printed to stderr immediately after each file. Watcher logs include elapsed time and page count at INFO level; warnings are promoted to WARNING level.
- **Q-4 Page-level partial recovery** — After Marker or Docling succeeds but produces sparse output (< 50 chars/page average), `_partial_recover()` extracts individual pages with pdfplumber and appends any page whose content was missing from the primary output. A warning is added to the result indicating how many pages were recovered.
- 12 new unit tests for quality scoring (boundary cases, scanned/warning flags, frontmatter emission) and partial recovery (healthy skip, missing-page append, no-metadata passthrough, pdfplumber error). Total: 275 unit tests, 78.7% coverage.

## [0.3.0] — 2026-04-07

### Added

#### Visual Enhancement Pipeline (VEP)
- **`[visual]` config section** with per-handler toggles (`enabled`, `classify`, `chart_description`, `diagram_to_mermaid`, `formula_to_latex`, `table_image_to_gfm`, `screenshot_description`); Mermaid and LaTeX off by default since not all renderers support those syntaxes
- **VEP-1: Visual element classifier** — classifies each extracted image as `chart | diagram | formula | table-image | screenshot | photo` using the configured AI provider; falls back to `photo` on any failure
- **VEP-2: Per-class enhancement handlers**
  - `chart` → prose paragraph describing chart type, axes, trend, and up to three key data points
  - `diagram` → Mermaid code block (`\`\`\`mermaid`) with structured-prose fallback if the model cannot produce valid Mermaid
  - `formula` → `$$...$$` LaTeX display-math block
  - `table-image` → GFM pipe table (validates `|` and `---` before replacing original ref)
  - `screenshot` → 2–3 sentence description of visible UI and content
  - `photo` → unchanged one-sentence alt-text (existing behaviour)
- **VEP-3: `VisualConfig` dataclass** in `config.py` — loaded from `[visual]` TOML section; injected into `Config`
- **VEP-4: Office embedded image extraction** — `_extract_docx_images()` and `_extract_pptx_images()` extract embedded images from DOCX and PPTX files via `python-docx` / `python-pptx` before the MarkItDown/Pandoc conversion pass; extracted images feed into the VEP pipeline; new optional extra `[office-images]`
- **VEP-5: pdfplumber tier image pass** — when the `pdfplumber` fallback is used and PyMuPDF is installed as a library, opportunistically extract PDF images via `image_extractor.py` to prevent silent image loss at the fallback tier

#### Workflow templates packaged inside the distribution
- Moved `services/Info.plist.template` and `services/document.wflow.template` into `src/drop2md/services/` so `pip install` includes them
- `install_quick_action` now loads templates via `importlib.resources.files("drop2md") / "services"` — works under pip, pipx, uvx, and `python -m drop2md.cli`
- `sys.executable` used directly for the Quick Action shell script path (replaced fragile `sys.argv[0]` + venv-bin-search logic)
- Quick Action log path changed from `/tmp/drop2mark.log` to `$HOME/Library/Logs/drop2md/drop2mark.log`; log directory created automatically

#### CLI
- `drop2md install-quick-action` — installs the **drop2mark** Finder Quick Action (`~/Library/Services/drop2mark.workflow`) for in-place document-to-markdown conversion via right-click in Finder
- `drop2md uninstall-quick-action` — removes the workflow bundle

#### Documentation
- `docs/ROADMAP.md` — versioned milestones (v0.3 → v0.4 → v1.0 → v2.0), competitive positioning, architecture decisions
- `docs/PRD.md` v2.0 — three personas, four-tier workflow table, full P0–P3 feature requirements, visual intelligence architecture diagram

### Fixed
- `_get_launchd_pid()` regex fix (was character-set stripping, not substring removal) — merged from v0.2.0

### Added (testing)
- 39 new unit tests in `tests/unit/test_vep.py` covering classifier, all five VEP handlers, `_apply_vep()`, `enhance()` entry point, `VisualConfig` TOML loading, office image extraction, and legacy PDF image pass
- Total: 246 unit tests, 77.95% coverage

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
