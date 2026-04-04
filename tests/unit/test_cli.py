"""Unit tests for the drop2md CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from drop2md import __version__
from drop2md.cli import app

runner = CliRunner()


@pytest.mark.unit
def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


@pytest.mark.unit
def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output
    assert "watch" in result.output


@pytest.mark.unit
def test_convert_missing_file(tmp_path):
    result = runner.invoke(app, ["convert", str(tmp_path / "ghost.pdf")])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@pytest.mark.unit
def test_convert_html_file(tmp_path, sample_html):
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["convert", str(sample_html), "--output", str(out), "--no-frontmatter"],
    )
    assert result.exit_code == 0, result.output
    md_files = list(out.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "Hello" in content


@pytest.mark.unit
def test_convert_with_frontmatter(tmp_path, sample_html):
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["convert", str(sample_html), "--output", str(out), "--frontmatter"],
    )
    assert result.exit_code == 0, result.output
    md_files = list(out.glob("*.md"))
    assert md_files[0].read_text().startswith("---\n")


@pytest.mark.unit
def test_convert_multiple_files(tmp_path):
    f1 = tmp_path / "a.html"
    f2 = tmp_path / "b.html"
    f1.write_text("<h1>A</h1>")
    f2.write_text("<h1>B</h1>")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["convert", str(f1), str(f2), "--output", str(out), "--no-frontmatter"],
    )
    assert result.exit_code == 0, result.output
    assert len(list(out.glob("*.md"))) == 2


@pytest.mark.unit
def test_convert_partial_failure(tmp_path):
    """One missing file should not prevent other files from converting."""
    good = tmp_path / "good.html"
    good.write_text("<h1>OK</h1>")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["convert", str(tmp_path / "missing.html"), str(good), "--output", str(out)],
    )
    assert result.exit_code == 1  # Overall failure due to missing file
    # But the good file should still have been converted
    assert len(list(out.glob("*.md"))) == 1


@pytest.mark.unit
def test_convert_uses_config(tmp_path):
    """Config file path is accepted without error."""
    cfg = tmp_path / "test.toml"
    cfg.write_text('[paths]\noutput_dir = "/tmp"\n')
    html = tmp_path / "test.html"
    html.write_text("<p>hi</p>")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["convert", str(html), "--config", str(cfg), "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
