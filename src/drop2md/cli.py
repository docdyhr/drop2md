"""drop2md CLI — typer-based command interface."""

from __future__ import annotations

import shutil
import sys
import uuid
from importlib.resources import files as _res_files
from pathlib import Path
from typing import Annotated

import typer

from drop2md import __version__

app = typer.Typer(
    name="drop2md",
    help="Convert documents to GFM markdown with macOS folder watching.",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"drop2md {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    pass


@app.command()
def convert(
    files: Annotated[list[Path], typer.Argument(help="File(s) to convert")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory (default: same as input)"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
    frontmatter: Annotated[bool, typer.Option(help="Add YAML frontmatter")] = True,
) -> None:
    """Convert one or more documents to GFM markdown."""
    from drop2md.config import load_config
    from drop2md.converters import ConversionError
    from drop2md.dispatcher import dispatch
    from drop2md.postprocess import postprocess
    from drop2md.utils.fs import atomic_write, safe_filename
    from drop2md.utils.logging import setup_logging

    cfg = load_config(config_path)
    setup_logging(cfg.logging.level, cfg.logging.file or None)

    errors = 0
    for file_path in files:
        if not file_path.exists():
            typer.echo(f"Error: {file_path} not found", err=True)
            errors += 1
            continue

        out_dir = output or cfg.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / safe_filename(file_path.name)

        try:
            typer.echo(f"Converting {file_path.name} ...", nl=False)
            result = dispatch(file_path, out_dir)

            if cfg.ollama.enabled:
                try:
                    from drop2md.enhance import enhance
                    result = enhance(result, cfg)
                except Exception as exc:
                    typer.echo(f" [enhance skipped: {exc}]", nl=False)

            md = postprocess(
                result,
                source=file_path,
                add_frontmatter=frontmatter,
                preserve_page_markers=cfg.output.preserve_page_markers,
            )
            atomic_write(out_path, md)
            typer.echo(f" → {out_path}  [{result.converter_used}]")
        except ConversionError as exc:
            typer.echo(f" FAILED: {exc}", err=True)
            errors += 1

    if errors:
        raise typer.Exit(1)


@app.command()
def watch(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
) -> None:
    """Watch the drop folder and convert documents automatically."""
    from drop2md.config import load_config
    from drop2md.utils.logging import setup_logging
    from drop2md.watcher import run_watcher

    cfg = load_config(config_path)
    setup_logging(cfg.logging.level, cfg.logging.file or None)
    run_watcher(cfg)


@app.command(name="install-service")
def install_service(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
) -> None:
    """Install drop2md as a macOS launchd background service."""
    import subprocess

    from drop2md.config import load_config

    if sys.platform != "darwin":
        typer.echo("Error: launchd service installation requires macOS", err=True)
        raise typer.Exit(1)

    cfg = load_config(config_path)
    cfg.ensure_dirs()

    # Locate the plist template
    template_path = Path(__file__).parent.parent.parent / "launchd" / "com.thomasdyhr.drop2md.plist.template"
    if not template_path.exists():
        typer.echo(f"Error: plist template not found at {template_path}", err=True)
        raise typer.Exit(1)

    python_path = sys.executable
    log_dir = Path("~/Library/Logs/drop2md").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")
    plist = (
        template
        .replace("__PYTHON_PATH__", str(python_path))
        .replace("__WATCH_DIR__", str(cfg.paths.watch_dir))
        .replace("__LOG_DIR__", str(log_dir))
    )
    if config_path:
        plist = plist.replace("__CONFIG_PATH__", str(config_path.resolve()))
    else:
        # Strip the --config <path> lines — no config arg → watcher uses env/defaults
        plist = "\n".join(
            line for line in plist.splitlines()
            if "--config" not in line and "__CONFIG_PATH__" not in line
        ) + "\n"

    agents_dir = Path("~/Library/LaunchAgents").expanduser()
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_dest = agents_dir / "com.thomasdyhr.drop2md.plist"
    plist_dest.write_text(plist, encoding="utf-8")

    result = subprocess.run(
        ["launchctl", "load", str(plist_dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        typer.echo(f"Warning: launchctl load returned {result.returncode}: {result.stderr}")
    else:
        typer.echo("Service installed and started.")
        typer.echo(f"  Plist:  {plist_dest}")
        typer.echo(f"  Watch:  {cfg.paths.watch_dir}")
        typer.echo(f"  Output: {cfg.paths.output_dir}")
        typer.echo(f"  Logs:   {log_dir}/drop2md.log")


@app.command(name="uninstall-service")
def uninstall_service() -> None:
    """Remove the drop2md launchd background service."""
    import subprocess

    if sys.platform != "darwin":
        typer.echo("Error: requires macOS", err=True)
        raise typer.Exit(1)

    plist_dest = Path("~/Library/LaunchAgents/com.thomasdyhr.drop2md.plist").expanduser()
    if not plist_dest.exists():
        typer.echo("Service not installed.")
        return

    subprocess.run(["launchctl", "unload", str(plist_dest)], check=False)
    plist_dest.unlink()
    typer.echo("Service removed.")


def _load_quick_action_templates() -> tuple[str, str]:
    """Load Info.plist and document.wflow templates from package data."""
    try:
        svc = _res_files("drop2md") / "services"
        info = (svc / "Info.plist.template").read_text(encoding="utf-8")
        wflow = (svc / "document.wflow.template").read_text(encoding="utf-8")
        return info, wflow
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"workflow template not found: {exc}") from exc


@app.command(name="install-quick-action")
def install_quick_action() -> None:
    """Install the drop2mark Finder Quick Action for in-place conversion."""
    if sys.platform != "darwin":
        typer.echo("Error: Quick Action installation requires macOS", err=True)
        raise typer.Exit(1)

    try:
        info_text, wflow_text = _load_quick_action_templates()
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    python_path = Path(sys.executable)

    wflow = (
        wflow_text
        .replace("__PYTHON_PATH__", str(python_path))
        .replace("__ACTION_UUID__", str(uuid.uuid4()).upper())
        .replace("__INPUT_UUID__", str(uuid.uuid4()).upper())
        .replace("__OUTPUT_UUID__", str(uuid.uuid4()).upper())
    )

    workflow_dir = Path("~/Library/Services/drop2mark.workflow/Contents").expanduser()
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "Info.plist").write_text(info_text, encoding="utf-8")
    (workflow_dir / "document.wflow").write_text(wflow, encoding="utf-8")

    typer.echo("Quick Action installed.")
    typer.echo(f"  Location: {workflow_dir.parent}")
    typer.echo(f"  Python:   {python_path}")
    typer.echo("")
    typer.echo("To enable: System Settings → Privacy & Security → Extensions → Finder")


@app.command(name="uninstall-quick-action")
def uninstall_quick_action() -> None:
    """Remove the drop2mark Finder Quick Action."""
    if sys.platform != "darwin":
        typer.echo("Error: requires macOS", err=True)
        raise typer.Exit(1)

    workflow_dest = Path("~/Library/Services/drop2mark.workflow").expanduser()
    if not workflow_dest.exists():
        typer.echo("Quick Action not installed.")
        return

    shutil.rmtree(workflow_dest)
    typer.echo("Quick Action removed.")


@app.command()
def check(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
) -> None:
    """Validate the full setup: config, converters, service, and AI enhancement."""
    import os
    import subprocess

    from drop2md.config import load_config

    n_ok = n_warn = n_fail = 0

    def _ok(label: str, detail: str = "") -> None:
        nonlocal n_ok
        n_ok += 1
        suffix = f"  {typer.style(detail, dim=True)}" if detail else ""
        typer.echo(f"  {typer.style('✓', fg=typer.colors.GREEN)}  {label}{suffix}")

    def _warn(label: str, hint: str = "") -> None:
        nonlocal n_warn
        n_warn += 1
        suffix = f"  {typer.style(hint, dim=True)}" if hint else ""
        typer.echo(f"  {typer.style('⚠', fg=typer.colors.YELLOW)}  {label}{suffix}")

    def _fail(label: str, hint: str = "") -> None:
        nonlocal n_fail
        n_fail += 1
        suffix = f"  {typer.style(hint, dim=True)}" if hint else ""
        typer.echo(f"  {typer.style('✗', fg=typer.colors.RED)}  {label}{suffix}")

    def _section(title: str) -> None:
        typer.echo(f"\n{typer.style(title, bold=True)}")

    # ── Config & directories ─────────────────────────────────────────────────
    _section("Config")

    resolved = config_path or Path("config.toml")
    if resolved.exists():
        _ok(str(resolved))
    elif config_path:
        _fail(f"{config_path} not found", "create config.toml from config.toml.example")
    else:
        _warn("No config.toml — running on defaults", "cp config.toml.example config.toml")

    cfg = load_config(config_path)

    for label, path in [("Watch dir ", cfg.paths.watch_dir), ("Output dir", cfg.paths.output_dir)]:
        if not path.exists():
            _warn(f"{label}  {path}  (will be created on first use)")
        elif not os.access(path, os.W_OK):
            _fail(f"{label}  {path}  (not writable)")
        else:
            _ok(f"{label}  {path}")

    # ── PDF converters ───────────────────────────────────────────────────────
    _section("PDF")

    from drop2md.converters.legacy_pdf import LegacyPdfConverter
    from drop2md.converters.pdf import DoclingPdfConverter, MarkerPdfConverter, PyMuPdfConverter

    if cfg.pdf.use_marker:
        if MarkerPdfConverter.is_available():
            _ok("marker       (enabled, installed)")
        else:
            _warn("marker       (enabled in config, not installed)", "pip install drop2md[pdf-ml]")
    else:
        _ok("marker       (disabled in config)")

    if cfg.pdf.use_docling:
        if DoclingPdfConverter.is_available():
            _ok("docling      (enabled, installed)")
        else:
            _warn("docling      (enabled in config, not installed)", "pip install drop2md[pdf-ml]")
    else:
        _ok("docling      (disabled in config)")

    if PyMuPdfConverter.is_available():
        _ok("pymupdf4llm  (installed)")
    else:
        _warn("pymupdf4llm  (not installed)", "pip install drop2md[pdf-light]")

    if LegacyPdfConverter.is_available():
        _ok("pdfplumber   (installed — baseline fallback)")
    else:
        _fail("pdfplumber   (not installed — no PDF conversion possible)", "pip install pdfplumber")

    # ── Office converters ────────────────────────────────────────────────────
    _section("Office  (DOCX / PPTX / XLSX)")

    from drop2md.converters.office import MarkItDownConverter, PandocOfficeConverter

    if cfg.office.use_markitdown:
        if MarkItDownConverter.is_available():
            _ok("markitdown   (enabled, installed)")
        else:
            _warn("markitdown   (enabled in config, not installed)", "pip install drop2md[office]")
    else:
        _ok("markitdown   (disabled in config)")

    if PandocOfficeConverter.is_available():
        _ok("pandoc       (installed — fallback converter)")
    else:
        _warn("pandoc       (not found — no fallback for office files)", "brew install pandoc")

    # ── HTML / EPUB ──────────────────────────────────────────────────────────
    _section("HTML / EPUB")

    from drop2md.converters.epub import EpubConverter
    from drop2md.converters.html import Html2TextConverter

    if Html2TextConverter.is_available():
        _ok("html2text    (installed)")
    else:
        _fail("html2text    (not installed — HTML conversion broken)", "pip install html2text")

    if EpubConverter.is_available():
        _ok("pandoc       (installed — EPUB supported)")
    else:
        _warn("pandoc       (not found — EPUB conversion unavailable)", "brew install pandoc")

    # ── OCR ──────────────────────────────────────────────────────────────────
    _section("OCR  (images / scanned PDFs)")

    from drop2md.converters.image import ImageConverter

    if not cfg.ocr.enabled:
        _ok("OCR disabled in config")
    else:
        if ImageConverter.is_available():
            _ok("pytesseract  (installed)")
        else:
            _warn("pytesseract  (not installed)", "pip install drop2md[ocr]")

        tess = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, check=False
        )
        if tess.returncode == 0:
            version = tess.stdout.splitlines()[0] if tess.stdout else "unknown"
            _ok(f"tesseract    ({version})")
        else:
            _warn("tesseract    (binary not found)", "brew install tesseract")

    # ── Service  (macOS only) ────────────────────────────────────────────────
    if sys.platform == "darwin":
        _section("Service")

        plist = Path("~/Library/LaunchAgents/com.thomasdyhr.drop2md.plist").expanduser()
        if not plist.exists():
            _warn("Not installed", "drop2md install-service --config <path>")
        else:
            _ok(f"Installed    ({plist})")
            lc = subprocess.run(
                ["launchctl", "list", "com.thomasdyhr.drop2md"],
                capture_output=True, text=True, check=False,
            )
            pid_line = next((l for l in lc.stdout.splitlines() if '"PID"' in l), None)
            if pid_line:
                pid = pid_line.strip().lstrip('"PID" = ').rstrip(";").strip()
                _ok(f"Running      (PID {pid})")
            else:
                _warn(
                    "Stopped",
                    "launchctl kickstart gui/$(id -u)/com.thomasdyhr.drop2md",
                )

    # ── AI enhancement ───────────────────────────────────────────────────────
    _section("Enhancement")

    if not cfg.ollama.enabled:
        _ok("Disabled in config  (set ollama.enabled = true to activate)")
    else:
        provider = getattr(cfg.ollama, "provider", "ollama")

        if provider == "ollama":
            try:
                import httpx
                r = httpx.get(f"{cfg.ollama.base_url}/api/tags", timeout=3)
                if r.status_code == 200:
                    _ok(f"Ollama       (running at {cfg.ollama.base_url})")
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    if any(cfg.ollama.model in m for m in models):
                        _ok(f"Model        {cfg.ollama.model}")
                    else:
                        available = ", ".join(m for m in models[:3]) or "none"
                        _warn(
                            f"Model        {cfg.ollama.model!r} not pulled",
                            f"ollama pull {cfg.ollama.model}  (available: {available})",
                        )
                else:
                    _fail(f"Ollama       (HTTP {r.status_code} from {cfg.ollama.base_url})")
            except Exception:
                _fail(
                    f"Ollama       (unreachable at {cfg.ollama.base_url})",
                    "ollama serve",
                )

        elif provider == "claude":
            try:
                import anthropic  # noqa: F401
                _ok("anthropic    (package installed)")
            except ImportError:
                _fail("anthropic    (not installed)", "pip install drop2md[claude]")
            api_key = getattr(cfg.ollama, "api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                _ok(f"API key      (set — model: {cfg.claude.model})")
            else:
                _fail("API key      (ANTHROPIC_API_KEY not set)", "export ANTHROPIC_API_KEY=sk-ant-...")

        elif provider in ("openai", "gemini"):
            try:
                import openai  # noqa: F401
                _ok("openai       (package installed)")
            except ImportError:
                _fail("openai       (not installed)", "pip install drop2md[openai]")
            env_key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
            api_key = getattr(cfg.ollama, "api_key", "") or os.environ.get(env_key, "")
            if api_key:
                _ok(f"API key      (set — model: {cfg.openai.model})")
            else:
                _fail(f"API key      ({env_key} not set)", f"export {env_key}=...")

        elif provider == "hf":
            try:
                import openai  # noqa: F401
                _ok("openai       (package installed — required for HuggingFace)")
            except ImportError:
                _fail("openai       (not installed)", "pip install drop2md[openai]")
            api_key = getattr(cfg.ollama, "api_key", "") or os.environ.get("HF_TOKEN", "")
            if api_key:
                _ok(f"HF_TOKEN     (set — model: {cfg.openai.model})")
            else:
                _fail("HF_TOKEN     (not set)", "export HF_TOKEN=hf_...")

        else:
            _warn(f"Unknown provider: {provider!r}")

    # ── Summary ──────────────────────────────────────────────────────────────
    typer.echo("")
    ok_s = typer.style(f"{n_ok} passed", fg=typer.colors.GREEN)
    warn_s = typer.style(f"{n_warn} warnings", fg=typer.colors.YELLOW)
    fail_s = typer.style(f"{n_fail} errors", fg=typer.colors.RED if n_fail else None)
    typer.echo(f"{ok_s}  ·  {warn_s}  ·  {fail_s}")

    if n_fail:
        raise typer.Exit(1)


def _get_launchd_pid() -> int | None:
    """Return the PID of the running launchd service, or None."""
    import re
    import subprocess

    plist = Path("~/Library/LaunchAgents/com.thomasdyhr.drop2md.plist").expanduser()
    if not plist.exists():
        return None
    lc = subprocess.run(
        ["launchctl", "list", "com.thomasdyhr.drop2md"],
        capture_output=True, text=True, check=False,
    )
    for line in lc.stdout.splitlines():
        m = re.search(r'"PID"\s*=\s*(\d+)', line)
        if m:
            return int(m.group(1))
    return None


def _render_status_panel(cfg: object, config_path: Path | None, launchd_pid: int | None) -> object:
    """Build a rich renderable with all status sections."""
    import datetime

    from rich.console import Group
    from rich.table import Table
    import rich.box

    from drop2md.config import Config

    assert isinstance(cfg, Config)

    lines: list[object] = []

    # ── Service state ───────────────────────────────────────────────────────
    plist = Path("~/Library/LaunchAgents/com.thomasdyhr.drop2md.plist").expanduser()
    if not plist.exists():
        svc_line = "not installed  (run: drop2md install-service)"
    elif launchd_pid is not None:
        svc_line = f"running  (PID {launchd_pid})"
    else:
        svc_line = "stopped  (run: launchctl kickstart gui/$UID/com.thomasdyhr.drop2md)"

    log_file = Path(cfg.logging.file).expanduser() if cfg.logging.file else None

    lines.append(f"Service:  {svc_line}")
    lines.append(f"Config:   {config_path or '(default)'}")
    lines.append(f"Watch:    {cfg.paths.watch_dir}")
    lines.append(f"Output:   {cfg.paths.output_dir}")
    lines.append(f"Log:      {log_file or '(stderr only)'}")

    # ── Recent conversions ──────────────────────────────────────────────────
    output_dir = cfg.paths.output_dir
    if output_dir.exists():
        md_files = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        if md_files:
            lines.append("")
            lines.append("Recent conversions:")
            for f in md_files:
                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"  {f.name:<45} {mtime}")
        else:
            lines.append("")
            lines.append("No conversions yet in output directory.")

    # ── AI enhancement ──────────────────────────────────────────────────────
    if cfg.ollama.enabled:
        try:
            import httpx
            r = httpx.get(f"{cfg.ollama.base_url}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                model_ok = any(cfg.ollama.model in m for m in models)
                model_status = f"{cfg.ollama.model} ✓" if model_ok else f"{cfg.ollama.model} (not pulled)"
                lines.append(f"\nOllama:   running  ({model_status})")
            else:
                lines.append(f"\nOllama:   unreachable at {cfg.ollama.base_url}")
        except Exception:
            lines.append(f"\nOllama:   unreachable at {cfg.ollama.base_url}")

    # ── Process resources ───────────────────────────────────────────────────
    lines.append("")
    lines.append("Process Resources")
    try:
        from drop2md.utils.process_monitor import sample_processes

        procs = sample_processes(launchd_pid)
        if procs:
            tbl = Table(box=rich.box.SIMPLE_HEAD, show_header=True, pad_edge=False)
            tbl.add_column("PID", style="dim", justify="right")
            tbl.add_column("Role", justify="left")
            tbl.add_column("Status", justify="left")
            tbl.add_column("CPU%", justify="right")
            tbl.add_column("RSS", justify="right")
            tbl.add_column("Mem%", justify="right")
            tbl.add_column("FDs", justify="right")
            tbl.add_column("Uptime", justify="left")
            for p in procs:
                fds = str(p.num_fds) if p.num_fds >= 0 else "—"
                tbl.add_row(
                    str(p.pid),
                    p.role,
                    p.status,
                    f"{p.cpu_pct:.1f}%",
                    f"{p.rss_mb:.0f} MB",
                    f"{p.mem_pct:.2f}%",
                    fds,
                    p.uptime,
                )
            lines.append(tbl)
            n = len(procs)
            lines.append(f"  {n} drop2md process{'es' if n != 1 else ''}")
        else:
            lines.append("  No drop2md processes found.")
            if plist.exists() and launchd_pid is None:
                lines.append("  [dim](service is installed but not running)[/dim]")
    except ImportError:
        lines.append("  (resource monitoring unavailable — pip install psutil)")

    return Group(*lines)


@app.command()
def status(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Refresh display every N seconds (like top)."),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", "-n", help="Refresh interval in seconds."),
    ] = 2.0,
) -> None:
    """Show drop2md service status, config, recent conversions, and process resources."""
    import time

    from rich.console import Console

    from drop2md.config import load_config

    cfg = load_config(config_path)

    if watch:
        from rich.live import Live

        console = Console()
        try:
            with Live(console=console, refresh_per_second=4) as live:
                while True:
                    pid = _get_launchd_pid()
                    live.update(_render_status_panel(cfg, config_path, pid))
                    time.sleep(interval)
        except KeyboardInterrupt:
            pass
    else:
        pid = _get_launchd_pid()
        Console().print(_render_status_panel(cfg, config_path, pid))


@app.command(name="install-mcp")
def install_mcp(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config.toml"),
    ] = None,
    claude_config: Annotated[
        Path | None,
        typer.Option("--claude-config", help="Path to Claude Desktop config.json (auto-detected if omitted)"),
    ] = None,
) -> None:
    """Register drop2md as an MCP server in Claude Desktop.

    Adds a 'drop2md' entry to claude_desktop_config.json and prints a reminder
    to restart Claude Desktop for the change to take effect.
    """
    import json

    # Auto-detect Claude Desktop config
    if claude_config is None:
        candidates = [
            Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser(),
        ]
        for c in candidates:
            if c.exists():
                claude_config = c
                break

    if claude_config is None or not claude_config.exists():
        typer.echo(
            "Error: Claude Desktop config not found. "
            "Pass --claude-config PATH to specify it.",
            err=True,
        )
        raise typer.Exit(1)

    python_path = sys.executable
    server_args: list[str] = ["-m", "drop2md.mcp_server"]
    if config_path:
        server_args += ["--config", str(config_path)]

    entry: dict = {
        "command": python_path,
        "args": server_args,
    }

    data = json.loads(claude_config.read_text(encoding="utf-8"))
    data.setdefault("mcpServers", {})

    if "drop2md" in data["mcpServers"]:
        typer.echo("Note: 'drop2md' entry already exists — updating it.")

    data["mcpServers"]["drop2md"] = entry

    # Write atomically
    tmp = claude_config.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=4), encoding="utf-8")
    tmp.rename(claude_config)

    typer.echo("MCP server registered in Claude Desktop config.")
    typer.echo(f"  Config: {claude_config}")
    typer.echo(f"  Python: {python_path}")
    typer.echo("")
    typer.echo("IMPORTANT: Restart Claude Desktop for the change to take effect.")
    typer.echo("  macOS: quit Claude Desktop from the menu bar and reopen it.")


@app.command(name="uninstall-mcp")
def uninstall_mcp(
    claude_config: Annotated[
        Path | None,
        typer.Option("--claude-config", help="Path to Claude Desktop config.json (auto-detected if omitted)"),
    ] = None,
) -> None:
    """Remove drop2md from Claude Desktop MCP servers."""
    import json

    if claude_config is None:
        candidate = Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser()
        if candidate.exists():
            claude_config = candidate

    if claude_config is None or not claude_config.exists():
        typer.echo("Error: Claude Desktop config not found.", err=True)
        raise typer.Exit(1)

    data = json.loads(claude_config.read_text(encoding="utf-8"))
    servers = data.get("mcpServers", {})

    if "drop2md" not in servers:
        typer.echo("drop2md is not registered in Claude Desktop.")
        return

    del servers["drop2md"]
    tmp = claude_config.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=4), encoding="utf-8")
    tmp.rename(claude_config)

    typer.echo("drop2md removed from Claude Desktop MCP servers.")
    typer.echo("Restart Claude Desktop for the change to take effect.")


if __name__ == "__main__":
    app()
