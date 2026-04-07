# drop2md — Product Roadmap

**Last updated:** 2026-04-07
**Current version:** 0.2.0
**Maintained by:** Thomas Juul Dyhr

---

## Executive Summary

drop2md is a macOS-native document-to-markdown converter built for developers
and knowledge workers who use LLMs daily. It converts PDF, DOCX, PPTX, XLSX,
HTML, EPUB, and images to clean GFM markdown with YAML frontmatter — the exact
format LLM tools consume best.

The strategic direction through v1.0 is **to become the best document converter
for macOS developers working with LLMs, competing on output quality and
macOS-native UX, not on enterprise features or cloud infrastructure.**

Two capabilities define that position:

1. **Visual intelligence** — AI that genuinely understands charts, diagrams,
   formulas, and table images rather than just captioning them.
2. **Workflow completeness** — the watcher, Quick Action, CLI, and MCP server
   positioned as a coherent four-tier system, not overlapping tools.

---

## Honest Current State

### What works well

- The four-tier PDF fallback chain (Marker → Docling → PyMuPDF4LLM → pdfplumber)
  is solid. Marker produces high-quality markdown for most born-digital PDFs
  without manual intervention.
- The multi-provider AI enhancement layer (Ollama, Claude, OpenAI, Gemini, HF)
  has clean architecture. The `AIProvider` protocol is easy to extend.
- macOS integration is genuinely differentiated: launchd daemon, Finder Quick
  Action, real-time status monitoring, MCP server for Claude Desktop. No
  comparable tool does all four.
- Test coverage at ~77%, CI green, ruff/mypy/bandit passing.
- The `drop2md check` command is excellent UX that no competitor ships.

### Where we fall short today

**Images are the biggest gap.** Marker extracts image PNGs and writes basic
alt-text. But charts have no data extracted. Diagrams are not converted to
Mermaid. Formulas are unsupported at every tier. Tables rendered as images
are silently dropped. Documents where visual elements carry the meaning produce
materially incomplete markdown.

**Office format visual content is completely absent.** MarkItDown extracts
text from DOCX/PPTX but embedded images and charts are never touched.

**The pdfplumber tier loses all images.** This tier is listed as "always
available fallback" but its output is significantly worse than implied for
visually-rich documents. Users hit this silently.

**No quality signal on output.** There is no way for a downstream tool or
pipeline to know whether a given conversion was high-quality or degraded.

**Configuration friction for non-developers.** Knowledge workers (Persona B)
still need to edit TOML files. The Quick Action has no configuration UI.

### Competitive position

| Tool | Formats | macOS UX | Local-first | AI enhancement | LLM-ready output |
|---|---|---|---|---|---|
| **drop2md** | PDF, Office, HTML, EPUB, Image | Full (daemon, Quick Action, MCP) | Yes | Multi-provider | Yes (frontmatter, GFM) |
| Marker | PDF only | CLI only | Yes (GPU) | No | Partial |
| Docling | PDF, DOCX | CLI/API only | Yes | No | Partial |
| MarkItDown | Office, PDF, HTML | None | Yes | No | Minimal |
| doc2md | PDF | None | Cloud optional | Vision-only | Minimal |
| LlamaParse | PDF, Office | Web UI / API | No (cloud) | Yes | Yes |
| Reducto | PDF, Office | Web UI / API | No (cloud) | Yes | Yes |

The moat is real: only drop2md combines local-first processing, macOS system
integration, multi-format support, and LLM-optimized output. The risk is that
the visual content gap narrows that moat for documents where charts and
diagrams carry the meaning.

---

## Architecture Decisions

### Decision 1: Watcher vs Quick Action — complementary, not redundant

These serve different jobs-to-be-done:

- **Quick Action = interactive tier.** The user has a file, decides to convert
  it now, gets a macOS notification. Natural for ad-hoc conversions and files
  received by download or email.
- **Watcher = automation tier.** Files arrive in the drop folder via scripts,
  scanner software, Hazel rules, Apple Shortcuts, or any automated process.
  No Finder interaction, no human decision required. 24/7 monitoring with
  backlog processing on startup.

A user whose scanner saves to a folder cannot use the Quick Action — there is
no human moment. A user doing a one-off conversion of a PDF attachment does not
want to configure a watch folder. These are genuinely different workflows. Both
are load-bearing for different personas.

**Going forward:** Documentation, README, and all user-facing copy explicitly
frames the four-tier workflow system (see PRD). The watcher is never described
as a fallback or legacy feature.

### Decision 2: Hybrid pipeline — native extraction for text, vision AI for visual elements

For born-digital PDFs, Marker/Docling are faster, cheaper, and more accurate
for text than any vision LLM. The 2025 research consensus confirms: PDF-native
extraction for text, vision AI for visual elements. Not either/or.

The correct architecture:
1. Native extraction runs first (existing pipeline — unchanged)
2. Extracted images are classified by type
3. Per-class AI enhancement produces the right markdown artifact

This is strictly additive. No changes to the converter chain itself.

### Decision 3: Visual intelligence is v0.3, not a v1.0 wishlist

The image gap is the single biggest quality deficiency in current output.
Shipping v1.0 with better distribution while visual content is still broken
would attract users who immediately hit the image-quality wall. Fix quality
before discoverability.

---

## Versioned Milestones

### v0.3 — Visual Intelligence

**Theme:** AI that understands what it sees, not just what it reads.

The current enhancement pipeline calls one function for all images: write a
one-sentence caption. v0.3 replaces this with a typed Visual Enhancement
Pipeline (VEP).

**VEP-1: Visual element classifier**
Given an extracted image, classify it as one of: `chart`, `diagram`,
`formula`, `table-image`, `screenshot`, `photo`. This classification drives all
downstream enhancement. Uses the existing `AIProvider` protocol — no new
provider infrastructure required. A single batch API call classifies all images
in the document to minimise round-trips.

**VEP-2: Per-class enhancement handlers**
- `chart` → extract type (bar/line/pie/scatter), axis labels, trend, key data
  points. Output: descriptive prose paragraph + optional structured comment.
- `diagram` (flowchart, sequence, ER) → attempt Mermaid code generation.
  Fallback to structured prose ("Three boxes labeled A, B, C with arrows A→B,
  B→C") if the model cannot produce valid Mermaid.
- `formula` → attempt LaTeX conversion. Output: `$$...$$` block.
- `table-image` → convert to GFM pipe table. Recovers content currently
  silently dropped.
- `screenshot` → descriptive paragraph of visible UI, content, and purpose.
- `photo` → one-sentence caption (current behavior, unchanged).

**VEP-3: `[visual]` config section**
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
Each handler independently toggleable. Mermaid and LaTeX off by default.

**VEP-4: Office embedded image extraction**
MarkItDown currently discards embedded images from DOCX and PPTX. Add an
extraction pass using `python-docx` / `python-pptx` before the MarkItDown
conversion. Extracted images feed into the VEP pipeline.
New optional extra: `[office-images]`.

**VEP-5: pdfplumber tier image pass**
When the pdfplumber fallback is used and PyMuPDF is available as a library,
run the image extraction pass from `image_extractor.py`. Prevents total image
loss at the fallback tier.

**Key files:**
- `src/drop2md/enhance.py` — VEP dispatcher and per-class handlers
- `src/drop2md/config.py` — new `VisualConfig` dataclass
- `src/drop2md/converters/office.py` — embedded image extraction
- `src/drop2md/converters/legacy_pdf.py` — pdfplumber image pass

**Success criteria:**
- A PDF containing a pie chart → output contains a prose paragraph describing
  chart type, approximate values, and dominant finding.
- A PPTX with embedded images → output contains extracted image refs with AI
  descriptions.
- A scanned table image → converts to a GFM pipe table (when model succeeds).
- Enhancement completes within 90 seconds for a 20-page document with 5 images.

---

### v0.4 — Quality & Robustness

**Theme:** Trustworthy output you can verify, not just output that exists.

**Q-1: Conversion quality scoring** ✅ *complete (v0.4)*
`score_quality()` in `postprocess.py` computes `high | medium | low` from
word count, heading density, image ref count, warning count, and scanned-PDF
flag. Written to YAML frontmatter as `quality:` on every conversion.

**Q-2: Scanned document detection and rerouting** ✅ *complete (v0.4)*
`_is_scanned_pdf()` samples the first 3 pages via pdfplumber; if total
character count < 20, Marker and Docling are skipped and a warning is added
to the result. PyMuPDF4LLM and pdfplumber still run as fallbacks.

**Q-3: Multi-page progress reporting** ✅ *complete (v0.4)*
CLI prints elapsed time and page count for docs > 10 pages; warnings printed
to stderr immediately. Watcher logs elapsed time, page count, and warnings at
appropriate log levels.

**Q-4: Page-level partial recovery** ✅ *complete (v0.4)*
`_partial_recover()` checks avg chars/page after Marker/Docling; if below
threshold, appends pdfplumber text for missing pages and adds a warning. Full
page-by-page Marker recovery remains future work (requires Marker internals).

**Q-5: RTF and ODT support** ✅ *complete (v0.4)*
`.rtf`, `.odt`, `.odp`, `.ods` and their MIME types now route to
`OfficeConverter`; the existing Pandoc fallback handles all four formats.

---

### v1.0 — Distribution & Onboarding

**Theme:** Install in 2 minutes, configured in 5, running in 10.

v1.0 is a polish and distribution release — making the tool ready for users
who did not write it.

**D-1: Homebrew formula**
Publish a Homebrew tap (`brew install docdyhr/tap/drop2md`). The formula
handles Python venv, system dependencies (pandoc, tesseract), Quick Action
install, and launchd registration. Target: zero terminal commands after
`brew install` for a knowledge worker.

**D-2: `drop2md setup` interactive wizard**
Guided command: config.toml creation, path selection, AI provider selection
with connection test, Quick Action and service install. No manual TOML editing
required for the standard path.

**D-3: GitHub Releases with prebuilt binary**
PyInstaller or Briefcase → macOS `.app` bundle and single-binary CLI. Users
without Python/pip install from a GitHub Release dmg.

**D-4: Obsidian vault integration**
`output.vault_dir` config option. Atomic-write output markdown directly into
an Obsidian vault in addition to the standard output directory.

**D-5: Coverage ≥ 85%, mypy strict clean**
v1.0 is a public release. The bar rises.

**D-6: Signed and notarized macOS package**
Apple Developer account required. Without notarization, macOS 13+ Gatekeeper
blocks the dmg installer for Persona B (knowledge workers) entirely.

---

### v2.0 — Platform Extensibility

**Theme:** drop2md as a platform, not just a tool.

**P-1: Plugin system**
Stable `BaseConverter` and `AIProvider` public API with semantic versioning.
Third-party converters register via pip entry points. Domain-specific visual
element pipelines (e.g., chess diagrams → FEN/PGN, musical notation → ABC)
belong as plugins, not in core.

**P-2: Webhook and event system**
Structured JSON event on each conversion completion. Targets: local HTTP
webhook (Zapier/n8n), Apple Shortcuts URL scheme, `NSUserNotification` with
structured metadata. Enables Hazel, Keyboard Maestro, and Apple Shortcuts to
build richer automation without polling the output directory.

**P-3: Conversion history and dashboard**
Local SQLite database of conversion events. FastAPI + htmx web UI to browse
history, retry failed conversions, view quality trends over time.

**P-4: Password-protected PDF handling**
Ghostscript integration for decryption before the converter chain runs.
Password supplied via config, keychain, or interactive prompt.

**P-5: Docker image for Linux/server deployment**
The watcher and CLI work on Linux with minor changes (no launchd, no Quick
Action). A Docker image allows use in server environments and CI pipelines.
This deliberately breaks the macOS-only constraint — but only for users who
opt into Docker.

---

## Priority Rationale

The sequencing follows one rule: **fix quality before fixing discoverability.**

1. **Output quality is the product.** A faster install path with worse markdown
   is not an improvement. Every feature that makes the markdown better comes
   before every feature that makes the tool easier to find.

2. **The automation tier and the interactive tier are both load-bearing.** The
   watcher is not legacy. It is the primary value proposition for users who
   want zero-touch conversion in scripted workflows. Do not let Quick Action
   success create pressure to deprecate it.

3. **The AI layer enhances, it does not replace.** Marker and Docling produce
   better text extraction than any vision LLM for born-digital PDFs. The AI
   layer adds value on top — it does not replace the extraction chain.

4. **Privacy-first is a genuine constraint, not marketing.** Every feature that
   adds a cloud dependency must have a local fallback or be explicitly opt-in.
   The Ollama → local model → cloud optional pattern must be preserved for
   every AI feature added.
