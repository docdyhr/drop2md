"""drop2md MCP Server — exposes document conversion to Claude Desktop.

Tools:
  convert_document  — convert a file to GFM markdown (returns text)
  list_converted    — list recent output files
  get_output_file   — read a specific converted markdown file

Resources:
  drop2md://output/{filename}  — serve a converted file as a resource

Run standalone:
  python -m drop2md.mcp_server       # stdio (for Claude Desktop)
  drop2md-mcp                        # via installed entry point
"""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from drop2md.config import load_config
from drop2md.converters import ConversionError
from drop2md.dispatcher import dispatch
from drop2md.postprocess import postprocess
from drop2md.utils.fs import atomic_write, safe_filename

log = logging.getLogger(__name__)

# Load config once at startup (reads config.toml or defaults)
_cfg = load_config()

mcp = FastMCP(
    "drop2md",
    instructions=(
        "drop2md converts documents (PDF, DOCX, PPTX, XLSX, HTML, EPUB, images) "
        "to GFM markdown. Use convert_document to convert a file and get the "
        "markdown text back. Use list_converted to see previously converted files. "
        "Use get_output_file to read a specific converted file by name."
    ),
)


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def convert_document(
    path: str,
    output_dir: str | None = None,
    add_frontmatter: bool = True,
) -> str:
    """Convert a document to GFM markdown and return the result.

    Args:
        path: Absolute or relative path to the source document.
              Supported: PDF, DOCX, PPTX, XLSX, HTML, EPUB, PNG, JPG.
        output_dir: Optional output directory (defaults to config output_dir).
                    Extracted images are saved to output_dir/images/.
        add_frontmatter: Whether to prepend YAML frontmatter (source, date, converter).

    Returns:
        The converted markdown text. Any extracted images are saved to disk
        and referenced with relative paths in the markdown.
    """
    src = Path(path).expanduser().resolve()
    if not src.exists():
        return f"Error: file not found: {path}"

    out_dir = Path(output_dir).expanduser() if output_dir else _cfg.paths.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / safe_filename(src.name)

    try:
        result = dispatch(src, out_dir)

        if _cfg.ollama.enabled:
            try:
                from drop2md.enhance import enhance
                result = enhance(result, _cfg)
            except Exception as exc:
                log.warning("Ollama enhancement failed: %s", exc)

        md = postprocess(
            result,
            source=src,
            add_frontmatter=add_frontmatter,
            preserve_page_markers=_cfg.output.preserve_page_markers,
        )
        atomic_write(out_path, md)
        log.info("MCP convert_document: %s → %s", src.name, out_path)

        if _cfg.output.vault_dir:
            vault_path = _cfg.output.vault_dir / out_path.name
            _cfg.output.vault_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(vault_path, md)
            log.info("MCP vault copy: %s", vault_path)

        return str(md)

    except ConversionError as exc:
        return f"Conversion failed: {exc}"
    except Exception as exc:
        log.exception("Unexpected error in convert_document for %s", path)
        return f"Unexpected error: {exc}"


@mcp.tool()
def list_converted(limit: int = 20) -> str:
    """List recently converted markdown files in the output directory.

    Args:
        limit: Maximum number of files to return (default 20).

    Returns:
        Markdown-formatted table of converted files with name, size, and date.
    """
    out_dir = _cfg.paths.output_dir
    if not out_dir.exists():
        return f"Output directory does not exist: {out_dir}"

    md_files = sorted(
        out_dir.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    if not md_files:
        return f"No converted files found in {out_dir}"

    lines = [
        f"## Converted files in `{out_dir}`\n",
        "| File | Size | Converted |",
        "|---|---|---|",
    ]
    for f in md_files:
        stat = f.stat()
        size_kb = stat.st_size / 1024
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        lines.append(f"| {f.name} | {size_kb:.1f} KB | {mtime} |")

    lines.append(f"\n*{len(md_files)} file(s) shown, output dir: `{out_dir}`*")
    return "\n".join(lines)


@mcp.tool()
def get_output_file(filename: str) -> str:
    """Read and return the contents of a converted markdown file.

    Args:
        filename: Name of the file in the output directory (e.g. 'report.md').
                  Can also be an absolute path.

    Returns:
        The markdown content of the file.
    """
    path = Path(filename)
    if not path.is_absolute():
        path = _cfg.paths.output_dir / filename

    if not path.exists():
        return f"File not found: {filename}"
    if path.suffix.lower() != ".md":
        return f"Not a markdown file: {filename}"

    return path.read_text(encoding="utf-8")


@mcp.tool()
def watch_status() -> str:
    """Show the current drop2md configuration and watcher status.

    Returns:
        Configuration summary showing watch dir, output dir, and enabled features.
    """
    import subprocess

    lines = [
        "## drop2md Configuration\n",
        f"- **Watch dir:** `{_cfg.paths.watch_dir}`",
        f"- **Output dir:** `{_cfg.paths.output_dir}`",
        f"- **PDF converters:** Marker={'enabled' if _cfg.pdf.use_marker else 'disabled'}, "
        f"Docling={'enabled' if _cfg.pdf.use_docling else 'disabled'}",
        f"- **Ollama:** {'enabled' if _cfg.ollama.enabled else 'disabled'}"
        + (f" ({_cfg.ollama.model})" if _cfg.ollama.enabled else ""),
        f"- **Frontmatter:** {'yes' if _cfg.output.add_frontmatter else 'no'}",
        "",
        "## Service Status\n",
    ]

    plist = Path("~/Library/LaunchAgents/com.thomasdyhr.drop2md.plist").expanduser()
    if plist.exists():
        result = subprocess.run(
            ["launchctl", "list", "com.thomasdyhr.drop2md"],
            capture_output=True, text=True, check=False,
        )
        lines.append(f"launchd service installed. `launchctl` output:\n```\n{result.stdout.strip()}\n```")
    else:
        lines.append("launchd service **not installed**. Run `drop2md install-service` to enable.")

    return "\n".join(lines)


# ─── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("drop2md://output/{filename}")
def output_resource(filename: str) -> str:
    """Serve a converted markdown file as an MCP resource.

    URI: drop2md://output/{filename}  (e.g. drop2md://output/report.md)
    """
    path = _cfg.paths.output_dir / filename
    if not path.exists():
        return f"# Not found\n\nFile `{filename}` does not exist in output dir."
    return str(path.read_text(encoding="utf-8"))


@mcp.resource("drop2md://config")
def config_resource() -> str:
    """Return the current drop2md configuration as markdown."""
    return str(watch_status())


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (for Claude Desktop)."""
    logging.basicConfig(level=logging.WARNING)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
