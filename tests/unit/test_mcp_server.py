"""Unit tests for the drop2md MCP server tools."""

from __future__ import annotations

import pytest


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Redirect the global _cfg output directory to tmp_path for isolation."""
    from drop2md import mcp_server
    monkeypatch.setattr(mcp_server._cfg.paths, "output_dir", tmp_path)
    return tmp_path


# ─── convert_document ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_convert_document_missing_file(tmp_path):
    """convert_document returns an error string for a missing file."""
    from drop2md.mcp_server import convert_document

    result = convert_document(str(tmp_path / "nonexistent.pdf"))
    assert result.startswith("Error")
    assert "not found" in result.lower()


@pytest.mark.unit
def test_convert_document_html(tmp_path):
    """convert_document converts a real HTML file and returns markdown."""
    from drop2md.mcp_server import convert_document

    html = tmp_path / "test.html"
    html.write_text("<html><body><h1>Hello</h1><p>World</p></body></html>", encoding="utf-8")

    result = convert_document(str(html), output_dir=str(tmp_path), add_frontmatter=False)
    assert "Hello" in result
    assert "World" in result


@pytest.mark.unit
def test_convert_document_with_frontmatter(tmp_path):
    """convert_document adds YAML frontmatter when requested."""
    from drop2md.mcp_server import convert_document

    html = tmp_path / "doc.html"
    html.write_text("<html><body><p>Text</p></body></html>", encoding="utf-8")

    result = convert_document(str(html), output_dir=str(tmp_path), add_frontmatter=True)
    assert result.startswith("---\n")
    assert 'source: "doc.html"' in result


@pytest.mark.unit
def test_convert_document_writes_output_file(tmp_path):
    """convert_document saves the .md file to the output directory."""
    from drop2md.mcp_server import convert_document

    html = tmp_path / "sample.html"
    html.write_text("<html><body><h2>Title</h2></body></html>", encoding="utf-8")

    convert_document(str(html), output_dir=str(tmp_path))
    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1


# ─── list_converted ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_list_converted_empty_dir(out_dir):
    """list_converted returns a helpful message when no files exist."""
    from drop2md.mcp_server import list_converted

    result = list_converted(limit=10)
    assert "No converted files" in result


@pytest.mark.unit
def test_list_converted_shows_files(out_dir):
    """list_converted returns a table of markdown files."""
    from drop2md.mcp_server import list_converted

    (out_dir / "report.md").write_text("# Report", encoding="utf-8")
    (out_dir / "notes.md").write_text("# Notes", encoding="utf-8")

    result = list_converted(limit=10)
    assert "report.md" in result
    assert "notes.md" in result


# ─── get_output_file ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_output_file_returns_content(out_dir):
    """get_output_file returns the markdown content of a file."""
    from drop2md.mcp_server import get_output_file

    (out_dir / "report.md").write_text("# Hello World\n", encoding="utf-8")

    result = get_output_file("report.md")
    assert "# Hello World" in result


@pytest.mark.unit
def test_get_output_file_missing(out_dir):
    """get_output_file returns an error message for missing files."""
    from drop2md.mcp_server import get_output_file

    result = get_output_file("missing.md")
    assert result == "File not found: missing.md"


@pytest.mark.unit
def test_get_output_file_rejects_non_markdown(out_dir):
    """get_output_file rejects non-.md files."""
    from drop2md.mcp_server import get_output_file

    (out_dir / "data.csv").write_text("a,b,c", encoding="utf-8")
    result = get_output_file(str(out_dir / "data.csv"))
    assert "Not a markdown file" in result


# ─── watch_status ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_watch_status_returns_config():
    """watch_status includes key config values."""
    from drop2md.mcp_server import watch_status

    result = watch_status()
    assert "Watch dir" in result
    assert "Output dir" in result


# ─── Resources ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_output_resource_returns_content(out_dir):
    """output_resource serves file content as a resource."""
    from drop2md.mcp_server import output_resource

    (out_dir / "test.md").write_text("# Resource Test\n", encoding="utf-8")

    result = output_resource("test.md")
    assert result == "# Resource Test\n"


@pytest.mark.unit
def test_output_resource_missing(out_dir):
    """output_resource returns a not-found message for missing files."""
    from drop2md.mcp_server import output_resource

    result = output_resource("ghost.md")
    assert "Not found" in result
    assert "ghost.md" in result
