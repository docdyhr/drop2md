# Testing Guide

Complete reference for testing doc2md — automated test suite, manual CLI verification,
MCP server interactive testing, watcher end-to-end, and AI provider validation.

---

## 1. Automated Test Suite

### Run everything

```bash
source .venv/bin/activate
pytest
```

### Targeted runs

```bash
# Fast unit tests only (no slow fixtures, ~8s)
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Single file or pattern
pytest tests/unit/test_mcp_server.py
pytest -k "test_convert"

# With verbose output
pytest -v

# See coverage gaps for a specific module
pytest --cov=doc2md.mcp_server --cov-report=term-missing -m unit
```

### Coverage threshold

`pytest.ini` enforces `--cov-fail-under=60`. The suite currently runs at ~73%.
Coverage XML is written to `coverage.xml` after every run.

---

## 2. CLI Manual Testing

### Basic conversion

```bash
# HTML
doc2md convert tests/fixtures/sample.pdf
doc2md convert tests/fixtures/sample.docx

# Specify output directory
doc2md convert tests/fixtures/sample.pdf --output /tmp/test-out/

# Suppress frontmatter
doc2md convert tests/fixtures/sample.pdf --no-frontmatter

# Multiple files
doc2md convert tests/fixtures/sample.pdf tests/fixtures/sample.docx --output /tmp/test-out/

# Use a specific config
doc2md convert tests/fixtures/sample.pdf --config config.toml
```

### Version and help

```bash
doc2md --version
doc2md --help
doc2md convert --help
doc2md watch --help
```

### Expected output

A successful conversion prints:

```
Converting sample.pdf ... → /path/to/output/sample.md
```

The `.md` file contains YAML frontmatter followed by GFM content:

```yaml
---
source: "sample.pdf"
converted: "2026-04-04T14:23:01"
converter: "pdfplumber"
pages: 1
---

# Annual Technical Report
...
```

---

## 3. Watcher Testing

### Foreground (terminal)

```bash
# Start the watcher — shows file events in real time
doc2md watch --config config.toml

# In a second terminal, drop a file into the watch dir:
cp tests/fixtures/sample.pdf ~/Documents/drop-to-md/

# You should see within ~2 seconds:
# [INFO] Processing sample.pdf
# [INFO] Wrote /Users/thomas/Documents/markdown-output/sample.md
```

### Disable AI enhancement for faster watcher tests

```bash
DOC2MD_OLLAMA_ENABLED=false doc2md watch --config config.toml
```

### launchd service status

```bash
doc2md status

# Show what launchctl knows about the service
launchctl list com.thomasdyhr.doc2md

# Tail the service log
tail -f ~/Library/Logs/doc2md/doc2md.log
```

---

## 4. MCP Server Testing

The MCP server exposes four tools and two resources to Claude Desktop.
There are three ways to test it.

### 4a. MCP Inspector (interactive web UI)

The MCP SDK ships an interactive inspector that lets you call tools
from a browser without opening Claude Desktop.

```bash
source .venv/bin/activate

# Start the inspector — opens http://localhost:5173 in your browser
mcp dev python -m doc2md.mcp_server
```

In the browser UI:

1. Select a tool from the sidebar (`convert_document`, `list_converted`, etc.)
2. Fill in the parameters
3. Click **Run** — the response appears on the right

**Quick test sequence in the inspector:**

| Tool | Parameters | Expected result |
|---|---|---|
| `convert_document` | `path=/tmp/test.html` | Error: file not found |
| `watch_status` | *(none)* | Config summary with watch/output dirs |
| `list_converted` | `limit=5` | Table of recent `.md` files (or empty message) |
| `convert_document` | `path=<absolute path to tests/fixtures/sample.pdf>` | Markdown text |
| `get_output_file` | `filename=sample.md` | Contents of the converted file |

### 4b. Automated pytest

The unit tests call the tool functions directly (no Claude Desktop needed):

```bash
pytest tests/unit/test_mcp_server.py -v
```

Expected output (11 tests):

```
tests/unit/test_mcp_server.py::test_convert_document_missing_file PASSED
tests/unit/test_mcp_server.py::test_convert_document_html PASSED
tests/unit/test_mcp_server.py::test_convert_document_with_frontmatter PASSED
tests/unit/test_mcp_server.py::test_convert_document_writes_output_file PASSED
tests/unit/test_mcp_server.py::test_list_converted_empty_dir PASSED
tests/unit/test_mcp_server.py::test_list_converted_shows_files PASSED
tests/unit/test_mcp_server.py::test_get_output_file_returns_content PASSED
tests/unit/test_mcp_server.py::test_get_output_file_missing PASSED
tests/unit/test_mcp_server.py::test_watch_status_returns_config PASSED
tests/unit/test_mcp_server.py::test_output_resource_returns_content PASSED
tests/unit/test_mcp_server.py::test_output_resource_missing PASSED
```

### 4c. Direct JSON-RPC over stdio

The server speaks JSON-RPC 2.0 over stdin/stdout. You can pipe messages directly:

```bash
# List all available tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python -m doc2md.mcp_server 2>/dev/null

# Call convert_document
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"convert_document","arguments":{"path":"/tmp/nonexistent.pdf"}}}' \
  | python -m doc2md.mcp_server 2>/dev/null

# Call watch_status
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"watch_status","arguments":{}}}' \
  | python -m doc2md.mcp_server 2>/dev/null
```

### 4d. Smoke-test the entry point

Before registering in Claude Desktop, verify the server starts cleanly:

```bash
# Should start silently (waiting for input on stdin — Ctrl-C to exit)
doc2md-mcp

# Or via the module
python -m doc2md.mcp_server
```

Any import error or config problem will appear immediately.

### 4e. End-to-end in Claude Desktop

The server is already registered. After restarting Claude Desktop,
ask Claude any of these prompts to exercise each tool:

```
Convert /Users/thomas/Downloads/report.pdf to markdown

List all recently converted files

Show me the contents of report.md

What is doc2md currently watching?
```

Claude Desktop logs: `~/Library/Logs/Claude/`
MCP calls are logged to: `~/Library/Logs/doc2md/doc2md.log` (if `[logging] file` is set)

---

## 5. AI Enhancement Testing

### Ollama (local)

```bash
# Check Ollama is running
curl -s http://localhost:11434/api/tags | python -m json.tool | grep name

# Convert with Ollama enabled
DOC2MD_OLLAMA_ENABLED=true \
  doc2md convert tests/fixtures/sample.pdf --config config.toml
```

### Claude (Anthropic)

```bash
# Requires: pip install doc2md[claude]
pip install -e ".[claude]"

DOC2MD_ENHANCE_PROVIDER=claude \
DOC2MD_OLLAMA_ENABLED=true \
ANTHROPIC_API_KEY=sk-ant-... \
  doc2md convert tests/fixtures/sample.pdf
```

### OpenAI

```bash
pip install -e ".[openai]"

DOC2MD_ENHANCE_PROVIDER=openai \
DOC2MD_OLLAMA_ENABLED=true \
OPENAI_API_KEY=sk-... \
  doc2md convert tests/fixtures/sample.pdf
```

### HuggingFace Inference Router

```bash
# Set base_url in [openai] section of config.toml, then:
DOC2MD_ENHANCE_PROVIDER=hf \
DOC2MD_OLLAMA_ENABLED=true \
HF_TOKEN=hf_... \
  doc2md convert tests/fixtures/sample.pdf
```

### Unit tests for enhancement providers (all mocked)

```bash
pytest tests/unit/test_enhance_providers.py -v
pytest tests/unit/test_enhance.py -v
```

### API key resolution order

For each provider, keys are resolved in this order:
1. `api_key` field in `[ollama]` section of `config.toml`
2. `DOC2MD_ENHANCE_API_KEY` environment variable
3. Provider native env var: `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `HF_TOKEN`

---

## 6. Converter-Specific Testing

### PDF tiers

```bash
# Force the legacy pdfplumber tier (fastest, always available)
python -c "
from doc2md.converters.legacy_pdf import LegacyPdfConverter
from pathlib import Path
r = LegacyPdfConverter().convert(Path('tests/fixtures/sample.pdf'), Path('/tmp'))
print(r.markdown[:500])
"

# Test whichever tier is active via the full dispatch
python -c "
from doc2md.dispatcher import dispatch
r = dispatch(Path('tests/fixtures/sample.pdf').resolve(), Path('/tmp'))
print(f'Converter: {r.converter_used}')
print(r.markdown[:500])
"
```

### Office (DOCX)

```bash
doc2md convert tests/fixtures/sample.docx --output /tmp/test-out/ --no-frontmatter
cat /tmp/test-out/sample.md
```

### Image OCR

```bash
# Requires: pip install doc2md[ocr]
doc2md convert tests/fixtures/sample.png --output /tmp/test-out/
cat /tmp/test-out/sample.md
# Should include OCR text: "doc2md Image OCR Test"
```

---

## 7. Regression Checklist

Run this checklist before tagging a release:

```bash
# 1. Full test suite with coverage
pytest

# 2. Lint
ruff check src/ tests/

# 3. Type check
mypy src/

# 4. Security audit
bandit -r src/
pip-audit

# 5. CLI smoke test
doc2md --version
doc2md convert tests/fixtures/sample.pdf --output /tmp/smoke-test/
cat /tmp/smoke-test/sample.md | head -20

# 6. MCP server starts cleanly
timeout 3 python -m doc2md.mcp_server; echo "Exit: $?"

# 7. MCP tools pass
pytest tests/unit/test_mcp_server.py -v
```
