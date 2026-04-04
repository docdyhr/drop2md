# doc2md — Ecosystem Comparison

A survey of open-source document-to-markdown tools: how they differ, where each excels,
and where this project (docdyhr/doc2md) fits in the landscape.

*Last updated: April 2026. Star counts are approximate at time of writing.*

---

## Overview

Converting documents to clean GitHub Flavored Markdown (GFM) has become a first-class
concern for LLM workflows. PDFs, DOCX files, and presentations need to reach Claude,
GPT-4, or a RAG pipeline in structured, token-efficient text — but the tools doing that
work range from one-file scripts to IBM-backed ML platforms.

The tradeoff is consistent across all projects: **accuracy and structure-awareness cost
weight**. The best PDF converters (Marker, Docling) require PyTorch and gigabytes of
model weights. The lightest tools (MarkItDown, robert-mcdermott/doc2md) are fast and
portable but produce lower-fidelity output for complex documents.

This project occupies a different niche altogether: it is not competing on raw conversion
accuracy but on **macOS automation** — watching a folder, running as a system service,
and integrating directly into Claude Desktop via MCP, with best-effort conversion quality
via a tiered fallback strategy.

---

## Quick Summary

| Project | Stars | Input formats | PDF approach | GPU needed | Folder watch | launchd | MCP | AI enhancement | License |
|---|---|---|---|---|---|---|---|---|---|
| **microsoft/markitdown** | ~93k | 15+ | Text extract + optional Azure OCR | No | No | No | No | OpenAI (optional) | MIT |
| **DS4SD/docling** | ~54k | 12+ | ML layout model + table detection | Optional | No | No | Yes | No | Apache 2.0 |
| **datalab-to/marker** | ~33k | 8 | Surya ML + OCR fallback | Yes (GPU/MPS) | No | No | No | Optional LLM | GPL v3 |
| **robert-mcdermott/doc2md** | ~28 | 6 (images + PDF) | Vision LLM per page | No | No | No | No | Core feature (vision) | Apache 2.0 |
| **docdyhr/doc2md** (this) | — | 11+ | Marker → Docling → PyMuPDF4LLM → pdfplumber | Optional (MPS) | Yes | Yes | Yes | Ollama / Claude / OpenAI / HF | MIT |

---

## Project Profiles

### microsoft/markitdown

[github.com/microsoft/markitdown](https://github.com/microsoft/markitdown) — ~93k stars, MIT

Microsoft's MarkItDown is the most widely adopted tool in this space. Its design
philosophy is *token efficiency over fidelity*: produce minimal, clean markdown that
LLMs can consume without wasting context. It supports an exceptional range of formats
(PDF, Word, PowerPoint, Excel, images, audio, YouTube URLs, ZIP archives) through a
modular plugin architecture — you install only what you need.

**Strengths:** Lightest dependency footprint; broadest format support; Microsoft-backed
with a large community; optional Azure Document Intelligence for high-quality OCR;
actively developed with frequent releases.

**Limitations:** PDF output quality is basic for complex layouts; table fidelity is
limited without Azure; vision features require an external OpenAI-compatible API; no
folder watching or service integration.

**Ideal for:** RAG pipelines, data ingestion, any project where format breadth and
minimal deps matter more than output fidelity.

---

### DS4SD/docling (IBM)

[github.com/DS4SD/docling](https://github.com/DS4SD/docling) — ~54k stars, Apache 2.0

IBM Research's Docling is the most capable open-source PDF understanding engine. It
detects page layout, reading order, table structure, formulas, and code blocks using
specialized ML models (TableFormer, layout models). It exports to Markdown, HTML, JSON,
and DocTags, and ships an MCP server for agentic workflows. It also handles financial
documents via XBRL support — a unique capability in this space.

**Strengths:** Best-in-class table and layout understanding; formula/math support;
XBRL financial documents; LangChain/LlamaIndex/Haystack integrations; MCP server;
Apache 2.0 license; LF AI & Data Foundation backing.

**Limitations:** Heavy — requires ML model files; setup is complex vs. lightweight
alternatives; primarily a Python API, not a user-facing automation tool; no macOS
service or folder watching.

**Ideal for:** Enterprise document workflows, scientific papers, financial reports,
teams with existing ML infrastructure.

---

### datalab-to/marker

[github.com/datalab-to/marker](https://github.com/datalab-to/marker) — ~33k stars, GPL v3

Marker is a high-throughput PDF conversion engine from Datalab. It pipelines `pdftext`
for native text extraction with Surya OCR as a fallback for scanned/image-heavy content,
and runs layout detection to correctly order columns, headers, and multi-column text.
Benchmarks show it outperforms Llamaparse, Mathpix, and most open-source alternatives
on accuracy. It processes ~25 pages/second on an H100 GPU.

**Strengths:** Best accuracy of any open-source PDF tool; excellent table and formula
preservation; batch processing; supports GPU, CPU, and Apple Silicon (MPS); optional
LLM enhancement for accuracy; structured JSON output.

**Limitations:** Requires PyTorch (~2–4GB download); peak 5GB GPU VRAM; GPL v3 license
(restrictive for commercial use); no service/automation layer; premium hosted API is
paid.

**Ideal for:** Teams processing large volumes of PDFs where accuracy is paramount and
GPU resources are available.

---

### robert-mcdermott/doc2md

[github.com/robert-mcdermott/doc2md](https://github.com/robert-mcdermott/doc2md) — ~28 stars, Apache 2.0

A minimal tool that takes a fundamentally different approach: it renders every page of
a PDF as an image, then sends each image to a vision-capable LLM (default: Ollama with
`qwen2.5vl`) and concatenates the text responses. This means it works on *any* PDF
regardless of text layer quality — even fully scanned documents — and requires no ML
models locally beyond access to an OpenAI-compatible API.

**Strengths:** Handles scanned/image-only PDFs with no text layer; extremely lightweight
(only `requests` + `PyMuPDF`); works with any OpenAI-compatible endpoint including local
Ollama; privacy-friendly; Apache 2.0.

**Limitations:** Output quality depends entirely on the vision model; no structure-aware
extraction (tables, headings, reading order); one API call per page — slow for long
documents; no folder watching, no service, no MCP, no frontmatter, no image extraction,
no batch processing; small community.

**Ideal for:** Scanned PDFs or image-heavy documents where a text layer is absent or
unreliable; users who already run Ollama locally and want a minimal tool.

> **Note on naming:** The name overlap with this project is coincidental. The two tools
> share no code and take completely different approaches.

---

### docdyhr/doc2md (this project)

[github.com/docdyhr/doc2md](https://github.com/docdyhr/doc2md) — v0.1.0, MIT

A macOS-first document automation system built around Claude Desktop integration.
Rather than picking a single conversion strategy, it runs a tiered waterfall
(Marker → Docling → PyMuPDF4LLM → pdfplumber) so output quality scales with however
much you choose to install — from zero optional deps to full ML stack. It wraps
conversion in a folder watcher, runs as a `launchd` service, and exposes all
functionality as MCP tools consumable directly inside Claude Desktop.

**Strengths:** `launchd` background service with native FSEvents watching (unique in
this space); first-class Claude Desktop MCP integration (`install-mcp`, `doc2md-mcp`);
multi-provider AI enhancement (Ollama, Claude, OpenAI, HuggingFace) with non-blocking
fallback; tiered PDF strategy adapts to installed deps; Apple Silicon MPS support;
GFM post-processing (table validation, heading normalisation, YAML frontmatter);
image extraction with optional vision captions; 80%+ test coverage; MIT core.

**Limitations:** macOS-only (launchd, FSEvents); v0.1.0 / single maintainer; no
formula/math support; no XBRL/financial document support; no cloud-hosted option;
Marker tier adds GPL v3 if installed.

**Ideal for:** macOS users who want documents to automatically appear as clean markdown
in their Claude Desktop context; LLM-centric workflows where the watcher/service layer
matters as much as conversion quality.

---

## Feature Matrix

| Feature | MarkItDown | Docling | Marker | robert-mcdermott | docdyhr/doc2md |
|---|---|---|---|---|---|
| **Input: PDF** | Text + optional OCR | ML layout + table | ML + Surya OCR | Vision LLM per page | Tiered (4 converters) |
| **Input: DOCX/PPTX/XLSX** | ✓ | ✓ | ✓ | ✗ | ✓ (MarkItDown + Pandoc) |
| **Input: HTML** | ✓ | ✗ | ✓ | ✗ | ✓ (html2text + Pandoc) |
| **Input: EPUB** | ✓ | ✗ | ✓ | ✗ | ✓ (Pandoc) |
| **Input: Images (OCR)** | ✓ (vision API) | ✓ | ✓ | ✓ (vision API) | ✓ (tesseract) |
| **Input: Audio/Video** | ✓ (transcription) | ✓ (WAV/MP3) | ✗ | ✗ | ✗ |
| **Input: Scanned PDFs** | Via Azure | ✓ | ✓ (Surya OCR) | ✓ (vision) | Via Marker/Docling |
| **Table quality** | Good | Excellent | Excellent | Model-dependent | Excellent (via Marker/Docling) |
| **Formula/math** | Limited | ✓ | ✓ | Model-dependent | ✗ |
| **Financial docs (XBRL)** | ✗ | ✓ | ✗ | ✗ | ✗ |
| **Image extraction** | ✗ | ✓ | ✓ | ✗ | ✓ (+ AI captions) |
| **YAML frontmatter** | ✗ | ✗ | ✗ | ✗ | ✓ |
| **GFM cleanup / normalise** | ✗ | ✗ | ✗ | ✗ | ✓ |
| **AI post-processing** | OpenAI (optional) | ✗ | LLM (optional) | Core (vision LLM) | Ollama/Claude/OpenAI/HF |
| **CLI** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Python API** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **MCP server** | ✗ | ✓ | ✗ | ✗ | ✓ (Claude Desktop) |
| **Folder watching** | ✗ | ✗ | ✗ | ✗ | ✓ (debounced) |
| **macOS launchd service** | ✗ | ✗ | ✗ | ✗ | ✓ |
| **Cross-platform** | ✓ | ✓ | ✓ | ✓ | ✗ (macOS only) |
| **GPU required** | No | Optional | Yes (MPS/CUDA/CPU) | No | Optional (MPS/CUDA/CPU) |
| **Approx. core install** | ~10MB | ~500MB+ | ~2–4GB | ~5MB | ~30MB |
| **License (core)** | MIT | Apache 2.0 | GPL v3 | Apache 2.0 | MIT |

---

## Decision Guide — When to Use Which

**1. Broadest format support, quickest setup, any OS**
→ **microsoft/markitdown**
Install in seconds, no optional deps required. Covers 15+ formats including audio,
YouTube, and ZIP archives. Perfect for data pipelines that need to ingest anything.

**2. Highest PDF accuracy, have a GPU or Apple Silicon**
→ **datalab-to/marker**
When tables, formulas, multi-column layout, and reading order must be preserved
faithfully and you can afford the PyTorch dependency and a GPU (or are willing to
run on MPS/CPU at reduced speed).

**3. Enterprise document processing, financial reports, or scientific papers**
→ **DS4SD/docling**
IBM Research backing, XBRL support, formula recognition, advanced layout detection,
and Apache 2.0 license. Best for structured data extraction and regulated industries.

**4. Scanned / image-only PDFs, minimal local deps, privacy-first**
→ **robert-mcdermott/doc2md**
If the PDF has no text layer, this tool's vision-LLM-per-page approach is the right
fit. Pairs naturally with a local Ollama instance for fully offline operation.

**5. macOS automation, Claude Desktop integration, LLM-driven workflows**
→ **docdyhr/doc2md (this project)**
Drop a file in a folder; it appears as clean markdown in Claude Desktop without any
manual steps. The MCP tools let Claude convert, list, and read documents directly.
The tiered PDF strategy means you get the best quality your installed stack allows,
always with a fallback to pdfplumber.

---

## Positioning Summary

docdyhr/doc2md is not trying to be the most accurate PDF converter or the most portable
utility. Its core proposition is **zero-friction document delivery to Claude Desktop on
macOS**.

The features that differentiate it from every project above are:

- **`launchd` service + debounced FSEvents watching** — no other tool in this space
  runs as a macOS background service that automatically processes a drop folder
- **`install-mcp` + MCP tools** — first-class Claude Desktop integration; Claude can
  call `convert_document`, `list_converted`, `get_output_file`, and `watch_status`
  directly without leaving the chat
- **Multi-provider AI enhancement with graceful fallback** — Ollama for free local
  processing, or swap to Claude Haiku / GPT-4o-mini / HuggingFace when speed matters;
  a provider being offline never blocks conversion
- **Tiered converter waterfall** — install nothing extra and get pdfplumber; install
  `[pdf-ml]` and get Marker + Docling quality; the same config works either way

The honest limitations are equally important: macOS only, v0.1.0, no formula support,
and the ML tiers (Marker, Docling) are large optional downloads. For cross-platform use
or formula-heavy documents, Docling or MarkItDown are better fits.
