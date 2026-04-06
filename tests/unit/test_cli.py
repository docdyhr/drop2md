"""Unit tests for the drop2md CLI."""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from drop2md import __version__
from drop2md.cli import app

runner = CliRunner()


# ── check command helpers ────────────────────────────────────────────────────


def _check_config(
    tmp_path: Path,
    *,
    ocr_enabled: bool = False,
    ollama_enabled: bool = False,
    ollama_model: str = "testmodel",
) -> Path:
    """Minimal config that disables optional converters and OCR by default."""
    watch = tmp_path / "watch"
    out = tmp_path / "out"
    watch.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    cfg = tmp_path / "check.toml"
    cfg.write_text(
        f'[paths]\nwatch_dir = "{watch}"\noutput_dir = "{out}"\n'
        "[pdf]\nuse_marker = false\nuse_docling = false\n"
        "[office]\nuse_markitdown = false\n"
        f"[ocr]\nenabled = {'true' if ocr_enabled else 'false'}\n"
        f"[ollama]\nenabled = {'true' if ollama_enabled else 'false'}\n"
        f'model = "{ollama_model}"\n'
    )
    return cfg


def _converter_patches(
    *,
    legacy: bool = True,
    pymupdf: bool = True,
    pandoc_office: bool = True,
    html2text: bool = True,
    epub: bool = True,
) -> list:
    return [
        patch(
            "drop2md.converters.legacy_pdf.LegacyPdfConverter.is_available",
            return_value=legacy,
        ),
        patch(
            "drop2md.converters.pdf.PyMuPdfConverter.is_available",
            return_value=pymupdf,
        ),
        patch(
            "drop2md.converters.office.PandocOfficeConverter.is_available",
            return_value=pandoc_office,
        ),
        patch(
            "drop2md.converters.html.Html2TextConverter.is_available",
            return_value=html2text,
        ),
        patch(
            "drop2md.converters.epub.EpubConverter.is_available",
            return_value=epub,
        ),
    ]


def _launchctl_result(pid: str | None = None) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = f'\t"PID" = {pid};\n' if pid else ""
    return m


def _invoke_check(tmp_path: Path, **patch_kwargs) -> object:
    """Invoke `drop2md check` with mocked converters and launchctl."""
    cfg_kwargs = {k: v for k, v in patch_kwargs.items() if k in ("ocr_enabled", "ollama_enabled", "ollama_model")}
    patch_kwargs = {k: v for k, v in patch_kwargs.items() if k not in cfg_kwargs}
    cfg = _check_config(tmp_path, **cfg_kwargs)
    patches = _converter_patches(**patch_kwargs)
    # Always mock subprocess.run so launchctl/tesseract don't hit real system
    lc_mock = _launchctl_result()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        return runner.invoke(app, ["check", "--config", str(cfg)])


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


# ── check command tests ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_help():
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "Validate" in result.output


@pytest.mark.unit
def test_check_all_ok(tmp_path):
    """All converters available, no failures → exit 0."""
    result = _invoke_check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "0 errors" in result.output
    assert "passed" in result.output


@pytest.mark.unit
def test_check_shows_config_found(tmp_path):
    """Config file found → shown as OK in output."""
    result = _invoke_check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "check.toml" in result.output


@pytest.mark.unit
def test_check_no_config_file(tmp_path):
    """When no --config is given and config.toml doesn't exist, warns but exits 0."""
    patches = _converter_patches()
    lc_mock = _launchctl_result()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        # Prevent picking up any real config.toml in cwd
        stack.enter_context(patch.dict(os.environ, {"DROP2MD_CONFIG": str(tmp_path / "nonexistent.toml")}))
        result = runner.invoke(app, ["check"])
    assert result.exit_code == 0, result.output
    assert "warnings" in result.output


@pytest.mark.unit
def test_check_explicit_config_not_found(tmp_path):
    """Explicit --config to missing file → _fail → exit 1."""
    missing = tmp_path / "no_such.toml"
    patches = _converter_patches()
    lc_mock = _launchctl_result()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        result = runner.invoke(app, ["check", "--config", str(missing)])
    assert result.exit_code == 1
    assert "not found" in result.output


@pytest.mark.unit
def test_check_pdfplumber_missing(tmp_path):
    """pdfplumber not installed → _fail → exit 1."""
    result = _invoke_check(tmp_path, legacy=False)
    assert result.exit_code == 1
    assert "errors" in result.output


@pytest.mark.unit
def test_check_html2text_missing(tmp_path):
    """html2text not installed → _fail → exit 1."""
    result = _invoke_check(tmp_path, html2text=False)
    assert result.exit_code == 1
    assert "errors" in result.output


@pytest.mark.unit
def test_check_pymupdf_missing_is_warning(tmp_path):
    """pymupdf4llm missing is a warning (not an error) → exit 0."""
    result = _invoke_check(tmp_path, pymupdf=False)
    assert result.exit_code == 0
    assert "warnings" in result.output


@pytest.mark.unit
def test_check_pandoc_missing_is_warning(tmp_path):
    """pandoc missing is a warning (not an error) → exit 0."""
    result = _invoke_check(tmp_path, pandoc_office=False, epub=False)
    assert result.exit_code == 0
    assert "warnings" in result.output


@pytest.mark.unit
def test_check_ocr_enabled_pytesseract_missing(tmp_path):
    """pytesseract missing when OCR enabled is a warning → exit 0."""
    cfg = _check_config(tmp_path, ocr_enabled=True)
    patches = _converter_patches()
    tess_proc = MagicMock()
    tess_proc.returncode = 1
    tess_proc.stdout = ""
    lc_mock = _launchctl_result()

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(
            patch("drop2md.converters.image.ImageConverter.is_available", return_value=False)
        )
        # subprocess.run side_effect: first call = tesseract, second = launchctl
        stack.enter_context(patch("subprocess.run", side_effect=[tess_proc, lc_mock]))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "warnings" in result.output


@pytest.mark.unit
def test_check_ocr_enabled_installed(tmp_path):
    """pytesseract + tesseract binary both present → no warnings for OCR."""
    cfg = _check_config(tmp_path, ocr_enabled=True)
    patches = _converter_patches()
    tess_proc = MagicMock()
    tess_proc.returncode = 0
    tess_proc.stdout = "tesseract 5.3.0\n"
    lc_mock = _launchctl_result()

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(
            patch("drop2md.converters.image.ImageConverter.is_available", return_value=True)
        )
        stack.enter_context(patch("subprocess.run", side_effect=[tess_proc, lc_mock]))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0, result.output


@pytest.mark.unit
def test_check_enhancement_disabled(tmp_path):
    """ollama.enabled = false → 'Disabled' shown, no HTTP call."""
    result = _invoke_check(tmp_path)
    assert "Disabled" in result.output


@pytest.mark.unit
def test_check_ollama_reachable(tmp_path):
    """Ollama enabled and reachable with correct model → exit 0."""
    cfg = _check_config(tmp_path, ollama_enabled=True, ollama_model="testmodel")
    patches = _converter_patches()
    lc_mock = _launchctl_result()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {"models": [{"name": "testmodel:latest"}]}

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        stack.enter_context(patch("httpx.get", return_value=http_response))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "0 errors" in result.output


@pytest.mark.unit
def test_check_ollama_unreachable(tmp_path):
    """Ollama enabled but unreachable → _fail → exit 1."""
    cfg = _check_config(tmp_path, ollama_enabled=True)
    patches = _converter_patches()
    lc_mock = _launchctl_result()

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        stack.enter_context(patch("httpx.get", side_effect=Exception("connection refused")))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 1
    assert "unreachable" in result.output


@pytest.mark.unit
def test_check_ollama_model_not_pulled(tmp_path):
    """Ollama running but model not pulled → warning, exit 0."""
    cfg = _check_config(tmp_path, ollama_enabled=True, ollama_model="missing-model")
    patches = _converter_patches()
    lc_mock = _launchctl_result()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {"models": [{"name": "other:latest"}]}

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        stack.enter_context(patch("httpx.get", return_value=http_response))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "warnings" in result.output


@pytest.mark.unit
@pytest.mark.skipif(os.sys.platform != "darwin", reason="Service section macOS only")
def test_check_service_not_installed(tmp_path, monkeypatch):
    """Service plist absent → warning, exit 0."""
    # Redirect HOME so plist path doesn't exist
    fake_home = tmp_path / "fake_home"
    (fake_home / "Library" / "LaunchAgents").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))

    cfg = _check_config(tmp_path)
    patches = _converter_patches()
    lc_mock = _launchctl_result()

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "Not installed" in result.output


@pytest.mark.unit
@pytest.mark.skipif(os.sys.platform != "darwin", reason="Service section macOS only")
def test_check_service_running(tmp_path, monkeypatch):
    """Service plist present and PID found → shown as running."""
    fake_home = tmp_path / "fake_home"
    agents = fake_home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.thomasdyhr.drop2md.plist").write_text("<plist/>")
    monkeypatch.setenv("HOME", str(fake_home))

    cfg = _check_config(tmp_path)
    patches = _converter_patches()
    lc_mock = _launchctl_result(pid="12345")

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "Running" in result.output or "12345" in result.output


@pytest.mark.unit
@pytest.mark.skipif(os.sys.platform != "darwin", reason="Service section macOS only")
def test_check_service_stopped(tmp_path, monkeypatch):
    """Service plist present but no PID → shown as stopped (warning)."""
    fake_home = tmp_path / "fake_home"
    agents = fake_home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.thomasdyhr.drop2md.plist").write_text("<plist/>")
    monkeypatch.setenv("HOME", str(fake_home))

    cfg = _check_config(tmp_path)
    patches = _converter_patches()
    lc_mock = _launchctl_result(pid=None)

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(patch("subprocess.run", return_value=lc_mock))
        result = runner.invoke(app, ["check", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "Stopped" in result.output or "warnings" in result.output


@pytest.mark.unit
def test_check_summary_counts(tmp_path):
    """Summary line always includes passed, warnings, and errors counts."""
    result = _invoke_check(tmp_path)
    out = result.output
    assert "passed" in out
    assert "warnings" in out
    assert "errors" in out


# ── status command tests ──────────────────────────────────────────────────────


def _status_config(tmp_path: Path) -> Path:
    """Minimal config for status tests."""
    watch = tmp_path / "watch"
    out = tmp_path / "out"
    watch.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    cfg = tmp_path / "status.toml"
    cfg.write_text(
        f'[paths]\nwatch_dir = "{watch}"\noutput_dir = "{out}"\n'
        "[pdf]\nuse_marker = false\nuse_docling = false\n"
        "[office]\nuse_markitdown = false\n"
        "[ocr]\nenabled = false\n"
        "[ollama]\nenabled = false\n"
    )
    return cfg


def _fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect HOME to tmp_path so no real plist is found."""
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.mark.unit
def test_status_watch_flag_in_help():
    """--watch flag appears in help text."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "--watch" in result.output
    assert "--interval" in result.output


@pytest.mark.unit
def test_status_no_service(tmp_path, monkeypatch):
    """No launchd plist → 'not installed', command exits cleanly."""
    _fake_home(tmp_path, monkeypatch)
    cfg = _status_config(tmp_path)
    monkeypatch.setattr(
        "drop2md.utils.process_monitor.sample_processes",
        lambda launchd_pid=None: [],
    )
    result = runner.invoke(app, ["status", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "not installed" in result.output


@pytest.mark.unit
def test_status_with_resources(tmp_path, monkeypatch):
    """When sample_processes returns data, PID and role appear in output."""
    from drop2md.utils.process_monitor import ProcessInfo

    _fake_home(tmp_path, monkeypatch)
    cfg = _status_config(tmp_path)
    # Create plist so service shows as "running"
    plist_dir = tmp_path / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True)
    (plist_dir / "com.thomasdyhr.drop2md.plist").write_text("<plist/>")
    monkeypatch.setattr("drop2md.cli._get_launchd_pid", lambda: 9552)
    monkeypatch.setattr(
        "drop2md.utils.process_monitor.sample_processes",
        lambda launchd_pid=None: [
            ProcessInfo(
                pid=9552,
                name="python3",
                role="watcher",
                status="running",
                cpu_pct=1.5,
                rss_mb=128.0,
                mem_pct=0.35,
                num_fds=23,
                uptime="2h 14m",
            )
        ],
    )
    result = runner.invoke(app, ["status", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "9552" in result.output
    assert "watcher" in result.output
    assert "2h 14m" in result.output


@pytest.mark.unit
def test_status_no_processes_found(tmp_path, monkeypatch):
    """When no drop2md processes are running, a friendly message is shown."""
    _fake_home(tmp_path, monkeypatch)
    cfg = _status_config(tmp_path)
    monkeypatch.setattr(
        "drop2md.utils.process_monitor.sample_processes",
        lambda launchd_pid=None: [],
    )
    result = runner.invoke(app, ["status", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "No drop2md processes found" in result.output


@pytest.mark.unit
def test_status_psutil_unavailable(tmp_path, monkeypatch):
    """If psutil is unavailable, status exits cleanly with a graceful note."""
    _fake_home(tmp_path, monkeypatch)
    cfg = _status_config(tmp_path)

    def _raise(launchd_pid: int | None = None) -> list:
        raise ImportError("psutil not installed")

    monkeypatch.setattr("drop2md.utils.process_monitor.sample_processes", _raise)
    result = runner.invoke(app, ["status", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "unavailable" in result.output
