# doc2md MCP Server — Claude Desktop Integration

The `doc2md` MCP server exposes document conversion as tools and resources
directly inside Claude Desktop. Once registered, you can ask Claude to convert
a file by name without switching to the terminal.

---

## Quick Setup

```bash
# Install the package (if not already done)
pip install -e ".[office,ocr]"

# Register in Claude Desktop (auto-detects config location)
doc2md install-mcp

# Restart Claude Desktop
# macOS: quit from the menu bar icon and reopen
```

After restarting, `doc2md` appears in Claude Desktop's MCP server list.

---

## Manual Registration

If `install-mcp` cannot find your Claude Desktop config, add the entry manually:

**Config file:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "doc2md": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "doc2md.mcp_server"]
    }
  }
}
```

Replace `/path/to/.venv/bin/python` with the output of:
```bash
which python   # (inside your activated venv)
```

---

## Available Tools

### `convert_document`

Convert a document to GFM markdown.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | string | required | Absolute path to the source file |
| `output_dir` | string | null | Override output directory |
| `add_frontmatter` | bool | true | Add YAML frontmatter block |

**Returns:** The full markdown text. Extracted images are saved to
`output_dir/images/` and referenced with relative paths.

**Example prompt:**
> "Convert `/Users/thomas/Downloads/report.pdf` to markdown"

---

### `list_converted`

List recently converted files in the output directory.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max files to show |

**Returns:** Markdown table with filename, size, and conversion date.

**Example prompt:**
> "What files have been converted recently?"

---

### `get_output_file`

Read the contents of a specific converted file.

| Parameter | Type | Description |
|---|---|---|
| `filename` | string | Filename in output dir (e.g. `report.md`) or absolute path |

**Returns:** Full markdown content of the file.

**Example prompt:**
> "Show me the contents of `report.md`"

---

### `watch_status`

Show the current configuration and launchd service status.

**Example prompt:**
> "What is doc2md watching?"

---

## Resources

Resources can be read directly in Claude's context:

| URI | Description |
|---|---|
| `doc2md://output/{filename}` | Read a converted markdown file |
| `doc2md://config` | Show current configuration |

---

## Example Workflow

```
You: Convert /Users/thomas/Downloads/Q1-Report.pdf

Claude: [calls convert_document]
        The file has been converted. Here's the result:
        ---
        source: "Q1-Report.pdf"
        converted: "2026-04-04T14:23:01"
        converter: "pdfplumber"
        pages: 18
        ---

        # Q1 Financial Report
        ...

You: List all converted files

Claude: [calls list_converted]
        | File | Size | Converted |
        |---|---|---|
        | Q1-Report.md | 42.3 KB | 2026-04-04 14:23 |
        ...
```

---

## Uninstall

```bash
doc2md uninstall-mcp
# Then restart Claude Desktop
```

---

## Testing the MCP Server

See [testing.md](testing.md#4-mcp-server-testing) for the full testing reference.
Quick summary:

```bash
# 1. Run the unit tests (no Claude Desktop needed)
pytest tests/unit/test_mcp_server.py -v

# 2. Interactive web inspector — calls tools from a browser UI
mcp dev python -m doc2md.mcp_server
# Opens http://localhost:5173

# 3. Smoke test the entry point (Ctrl-C to exit)
doc2md-mcp
```

---

## Troubleshooting

**Server not appearing in Claude Desktop**
- Check Claude Desktop logs: `~/Library/Logs/Claude/`
- Verify the Python path in the config is correct and the venv is activated
- Run `doc2md-mcp` directly in terminal to check for import errors

**"Module not found" errors**
- The `command` in the config must point to the Python inside the venv where `doc2md` is installed
- Run `which python` inside the venv to get the correct path

**Conversion fails**
- Run `doc2md convert /path/to/file.pdf` in terminal to see the full error
- Check `~/Library/Logs/doc2md/doc2md.log` for details

**Images not found**
- Images are saved to `{output_dir}/images/` with relative paths in the markdown
- Claude Desktop can view these images if you open the markdown file as an artifact
