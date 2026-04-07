# TODO — drop2md

Derived from [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`docs/PRD.md`](docs/PRD.md).
Current version: **0.3.0**

---

## v0.3 — Visual Intelligence

> Theme: AI that understands what it sees, not just what it reads.
> Key files: `src/drop2md/enhance.py`, `src/drop2md/config.py`, `src/drop2md/converters/office.py`, `src/drop2md/converters/legacy_pdf.py`

### Visual Enhancement Pipeline (VEP)

- [x] **VEP-1** `enhance.py` — Add `classify_visual_elements()`: single batch API call classifies all extracted images as `chart | diagram | formula | table-image | screenshot | photo`
- [x] **VEP-2a** `enhance.py` — `describe_chart()` handler: extracts chart type, axis labels, trend, key data points → prose paragraph + optional `<!-- chart-data: -->` comment
- [x] **VEP-2b** `enhance.py` — `diagram_to_mermaid()` handler: flowchart/sequence/ER → Mermaid code; prose fallback if model output is invalid
- [x] **VEP-2c** `enhance.py` — `formula_to_latex()` handler: mathematical expressions → `$$...$$` block
- [x] **VEP-2d** `enhance.py` — `table_image_to_gfm()` handler: table rendered as image → GFM pipe table
- [x] **VEP-2e** `enhance.py` — `describe_screenshot()` handler: UI/interface description in prose
- [x] **VEP-3** `config.py` — Add `VisualConfig` dataclass and `[visual]` TOML section with per-handler toggles (`diagram_to_mermaid` and `formula_to_latex` default `false`)
- [x] **VEP-4** `converters/office.py` — Extract embedded images from DOCX (`python-docx`) and PPTX (`python-pptx`) before MarkItDown pass; feed images into VEP
- [x] **VEP-5** `converters/legacy_pdf.py` — Run `image_extractor.py` image pass when PyMuPDF is available, preventing total image loss at the pdfplumber fallback tier
- [x] `pyproject.toml` — Add `[office-images]` optional extra (`python-docx`, `python-pptx`)

### Tests

- [x] Unit tests for each VEP handler (mocked AI provider)
- [x] Unit tests for `VisualConfig` loading and per-handler toggle behaviour
- [ ] Integration smoke test: PDF with chart → output contains prose description
- [ ] Integration smoke test: PPTX with embedded image → image extracted and described

---

## v0.4 — Quality & Robustness

> Theme: Trustworthy output you can verify, not just output that exists.
> Key files: `src/drop2md/postprocess.py`, `src/drop2md/converters/pdf.py`, `src/drop2md/dispatcher.py`

- [ ] **Q-1** `postprocess.py` — Compute `quality: high | medium | low` score (heading density, table count, image ref count, word count ratio, warning count) and write to YAML frontmatter
- [ ] **Q-2** `converters/pdf.py` — Scanned document detection: check character density of first N pages; route image-only PDFs to vision-LLM primary path before running Marker
- [ ] **Q-3** `cli.py`, `watcher.py` — Multi-page progress reporting for documents > 10 pages: converter tier, page N of M, elapsed time
- [ ] **Q-4** `converters/pdf.py` — Page-level partial recovery: keep Marker output for successful pages, fall back to pdfplumber only for failing pages, merge results
- [ ] **Q-5** `dispatcher.py` — RTF and ODT support via Pandoc fallback (add to `_EXT_MAP` and `_MIME_MAP`)

### Tests

- [ ] Unit tests for quality scorer with known inputs (high/medium/low boundary cases)
- [ ] Unit test for scanned document detection (mock PDF with zero character density)
- [ ] Unit test for RTF/ODT dispatcher routing

---

## v1.0 — Distribution & Onboarding

> Theme: Install in 2 minutes, configured in 5, running in 10.

- [ ] **D-1** Homebrew formula and tap: `brew install docdyhr/tap/drop2md` (handles venv, pandoc, tesseract, Quick Action, launchd)
- [ ] **D-2** `cli.py` — `drop2md setup` interactive wizard: config.toml creation, AI provider selection + connection test, Quick Action + service install; no manual TOML editing required
- [ ] **D-3** GitHub Releases prebuilt binary: PyInstaller or Briefcase → `.app` bundle + single-binary CLI dmg
- [ ] **D-4** `config.py` — `output.vault_dir` option: atomic-write output into an Obsidian vault directory
- [ ] **D-5** Raise test coverage floor to ≥ 85%; resolve all mypy strict violations
- [ ] **D-6** Sign and notarize the macOS package (Apple Developer account required; Gatekeeper blocks unsigned dmg on macOS 13+)

---

## v2.0 — Platform Extensibility

> Theme: drop2md as a platform, not just a tool.

- [ ] **P-1** Plugin system: stable `BaseConverter` + `AIProvider` public API with semantic versioning; third-party converters register via pip entry points
- [ ] **P-2** Webhook and event system: structured JSON event per conversion; HTTP webhook, Apple Shortcuts URL scheme, `NSUserNotification` with structured metadata
- [ ] **P-3** Conversion history: local SQLite database of events; FastAPI + htmx dashboard (browse history, retry failures, quality trends)
- [ ] **P-4** Password-protected PDF handling via ghostscript (password from config, keychain, or interactive prompt)
- [ ] **P-5** Docker image for Linux/server deployment (watcher + CLI, no launchd/Quick Action)

---

## Ongoing / Cross-cutting

- [ ] Keep `docs/ROADMAP.md`, `docs/PRD.md`, `CHANGELOG.md`, and `README.md` in sync with each release
- [ ] Maintain CI green on every commit (ruff, mypy, pytest, bandit, pip-audit)
- [ ] Privacy invariant: every new AI-dependent feature must have a local fallback or be explicitly opt-in
