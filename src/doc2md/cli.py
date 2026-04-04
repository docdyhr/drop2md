"""doc2md CLI — typer-based command interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from doc2md import __version__

app = typer.Typer(
    name="doc2md",
    help="Convert documents to GFM markdown with macOS folder watching.",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"doc2md {__version__}")
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
    from doc2md.config import load_config
    from doc2md.converters import ConversionError
    from doc2md.dispatcher import dispatch
    from doc2md.postprocess import postprocess
    from doc2md.utils.fs import atomic_write, safe_filename
    from doc2md.utils.logging import setup_logging

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
                    from doc2md.ollama_enhance import enhance
                    result = enhance(result, cfg)
                except Exception as exc:
                    typer.echo(f" [Ollama skipped: {exc}]", nl=False)

            md = postprocess(
                result,
                source=file_path,
                add_frontmatter=frontmatter,
                preserve_page_markers=cfg.output.preserve_page_markers,
            )
            atomic_write(out_path, md)
            typer.echo(f" → {out_path}")
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
    from doc2md.config import load_config
    from doc2md.utils.logging import setup_logging
    from doc2md.watcher import run_watcher

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
    """Install doc2md as a macOS launchd background service."""
    import subprocess

    from doc2md.config import load_config

    if sys.platform != "darwin":
        typer.echo("Error: launchd service installation requires macOS", err=True)
        raise typer.Exit(1)

    cfg = load_config(config_path)
    cfg.ensure_dirs()

    # Locate the plist template
    template_path = Path(__file__).parent.parent.parent / "launchd" / "com.thomasdyhr.doc2md.plist.template"
    if not template_path.exists():
        typer.echo(f"Error: plist template not found at {template_path}", err=True)
        raise typer.Exit(1)

    python_path = sys.executable
    log_dir = Path("~/Library/Logs/doc2md").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")
    plist = (
        template
        .replace("__PYTHON_PATH__", str(python_path))
        .replace("__WATCH_DIR__", str(cfg.paths.watch_dir))
        .replace("__LOG_DIR__", str(log_dir))
        .replace("__CONFIG_PATH__", str(config_path or ""))
    )

    agents_dir = Path("~/Library/LaunchAgents").expanduser()
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_dest = agents_dir / "com.thomasdyhr.doc2md.plist"
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
        typer.echo(f"  Logs:   {log_dir}/doc2md.log")


@app.command(name="uninstall-service")
def uninstall_service() -> None:
    """Remove the doc2md launchd background service."""
    import subprocess

    if sys.platform != "darwin":
        typer.echo("Error: requires macOS", err=True)
        raise typer.Exit(1)

    plist_dest = Path("~/Library/LaunchAgents/com.thomasdyhr.doc2md.plist").expanduser()
    if not plist_dest.exists():
        typer.echo("Service not installed.")
        return

    subprocess.run(["launchctl", "unload", str(plist_dest)], check=False)
    plist_dest.unlink()
    typer.echo("Service removed.")


@app.command()
def status() -> None:
    """Show doc2md service status."""
    import subprocess

    plist_dest = Path("~/Library/LaunchAgents/com.thomasdyhr.doc2md.plist").expanduser()
    if not plist_dest.exists():
        typer.echo("Service not installed. Run: doc2md install-service")
        return

    result = subprocess.run(
        ["launchctl", "list", "com.thomasdyhr.doc2md"],
        capture_output=True,
        text=True,
        check=False,
    )
    typer.echo(result.stdout or "Service not running.")


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
    """Register doc2md as an MCP server in Claude Desktop.

    Adds a 'doc2md' entry to claude_desktop_config.json and prints a reminder
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
    server_args: list[str] = ["-m", "doc2md.mcp_server"]
    if config_path:
        server_args += ["--config", str(config_path)]

    entry: dict = {
        "command": python_path,
        "args": server_args,
    }

    data = json.loads(claude_config.read_text(encoding="utf-8"))
    data.setdefault("mcpServers", {})

    if "doc2md" in data["mcpServers"]:
        typer.echo("Note: 'doc2md' entry already exists — updating it.")

    data["mcpServers"]["doc2md"] = entry

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
    """Remove doc2md from Claude Desktop MCP servers."""
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

    if "doc2md" not in servers:
        typer.echo("doc2md is not registered in Claude Desktop.")
        return

    del servers["doc2md"]
    tmp = claude_config.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=4), encoding="utf-8")
    tmp.rename(claude_config)

    typer.echo("doc2md removed from Claude Desktop MCP servers.")
    typer.echo("Restart Claude Desktop for the change to take effect.")
