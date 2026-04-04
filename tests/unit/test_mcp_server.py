"""Unit tests for the doc2md MCP server tools."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_convert_document_missing_file(tmp_path):
    """convert_document returns an error string for a missing file."""
    from doc2md.mcp_server import convert_document

    result = convert_document(str(tmp_path / "nonexistent.pdf"))
    assert "Error" in result or "not found" in result.lower()


@pytest.mark.unit
def test_convert_document_html(tmp_path):
    """convert_document converts a real HTML file and returns markdown."""
    from doc2md.mcp_server import convert_document

    html = tmp_path / "test.html"
    html.write_text(
        "<html><body><h1>Hello</h1><p>World</p></body></html>",
        encoding="utf-8",
    )

    result = convert_document(str(html), output_dir=str(tmp_path), add_frontmatter=False)
    assert "Hello" in result
    assert "World" in result


@pytest.mark.unit
def test_convert_document_with_frontmatter(tmp_path):
    """convert_document adds YAML frontmatter when requested."""
    from doc2md.mcp_server import convert_document

    html = tmp_path / "doc.html"
    html.write_text("<html><body><p>Text</p></body></html>", encoding="utf-8")

    result = convert_document(str(html), output_dir=str(tmp_path), add_frontmatter=True)
    assert result.startswith("---\n")
    assert 'source: "doc.html"' in result


@pytest.mark.unit
def test_convert_document_writes_output_file(tmp_path):
    """convert_document saves the .md file to the output directory."""
    from doc2md.mcp_server import convert_document

    html = tmp_path / "sample.html"
    html.write_text("<html><body><h2>Title</h2></body></html>", encoding="utf-8")

    convert_document(str(html), output_dir=str(tmp_path))
    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1


@pytest.mark.unit
def test_list_converted_empty_dir(tmp_path):
    """list_converted returns a helpful message when no files exist."""
    from doc2md.mcp_server import _cfg, list_converted

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = list_converted(limit=10)
        assert "No converted files" in result or str(tmp_path) in result
    finally:
        _cfg.paths.output_dir = original


@pytest.mark.unit
def test_list_converted_shows_files(tmp_path):
    """list_converted returns a table of markdown files."""
    from doc2md.mcp_server import _cfg, list_converted

    # Create some fake output files
    (tmp_path / "report.md").write_text("# Report", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# Notes", encoding="utf-8")

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = list_converted(limit=10)
        assert "report.md" in result
        assert "notes.md" in result
    finally:
        _cfg.paths.output_dir = original


@pytest.mark.unit
def test_get_output_file_returns_content(tmp_path):
    """get_output_file returns the markdown content of a file."""
    from doc2md.mcp_server import _cfg, get_output_file

    md = tmp_path / "report.md"
    md.write_text("# Hello World\n", encoding="utf-8")

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = get_output_file("report.md")
        assert "# Hello World" in result
    finally:
        _cfg.paths.output_dir = original


@pytest.mark.unit
def test_get_output_file_missing(tmp_path):
    """get_output_file returns an error message for missing files."""
    from doc2md.mcp_server import _cfg, get_output_file

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = get_output_file("missing.md")
        assert "not found" in result.lower() or "File not found" in result
    finally:
        _cfg.paths.output_dir = original


@pytest.mark.unit
def test_watch_status_returns_config(tmp_path):
    """watch_status includes key config values."""
    from doc2md.mcp_server import watch_status

    result = watch_status()
    assert "doc2md" in result.lower() or "Watch dir" in result or "Output dir" in result


@pytest.mark.unit
def test_output_resource_returns_content(tmp_path):
    """output_resource serves file content as a resource."""
    from doc2md.mcp_server import _cfg, output_resource

    md = tmp_path / "test.md"
    md.write_text("# Resource Test\n", encoding="utf-8")

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = output_resource("test.md")
        assert "# Resource Test" in result
    finally:
        _cfg.paths.output_dir = original


@pytest.mark.unit
def test_output_resource_missing(tmp_path):
    """output_resource returns a not-found message for missing files."""
    from doc2md.mcp_server import _cfg, output_resource

    original = _cfg.paths.output_dir
    _cfg.paths.output_dir = tmp_path
    try:
        result = output_resource("ghost.md")
        assert "not found" in result.lower() or "Not found" in result
    finally:
        _cfg.paths.output_dir = original
