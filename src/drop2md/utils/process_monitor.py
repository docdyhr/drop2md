"""Process resource monitoring for drop2md-related processes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ProcessInfo:
    pid: int
    name: str
    role: str  # "watcher" | "mcp-server" | "converter" | "unknown"
    status: str  # psutil status: "running", "sleeping", "zombie", etc.
    cpu_pct: float
    rss_mb: float
    mem_pct: float
    num_fds: int
    uptime: str  # e.g. "2h 14m", "45m 3s", "3d 7h"


def _infer_role(cmdline: list[str]) -> str:
    joined = " ".join(cmdline)
    if "mcp_server" in joined or "mcp-server" in joined:
        return "mcp-server"
    args = cmdline[1:]  # skip interpreter
    if "watch" in args:
        return "watcher"
    if "convert" in args:
        return "converter"
    return "unknown"


def _format_uptime(create_time: float) -> str:
    seconds = int(time.time() - create_time)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    if seconds < 86400:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}h {m}m"
    d, rem = divmod(seconds, 86400)
    h = rem // 3600
    return f"{d}d {h}h"


def _collect_procs(launchd_pid: int | None) -> list[Any]:
    """Return deduplicated list of psutil.Process objects for drop2md."""
    import psutil  # late import so module is importable without psutil installed

    found: dict[int, Any] = {}

    # Primary: launchd-managed root + children
    if launchd_pid is not None:
        try:
            root = psutil.Process(launchd_pid)
            found[root.pid] = root
            for child in root.children(recursive=True):
                found[child.pid] = child
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Fallback / supplement: cmdline scan
    try:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"] or []
                if any("drop2md" in arg for arg in cmdline):
                    if proc.pid not in found:
                        found[proc.pid] = proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

    return list(found.values())


def sample_processes(launchd_pid: int | None = None) -> list[ProcessInfo]:
    """CPU-sampled snapshot of all drop2md processes.

    Does two cpu_percent polls with a 0.2s sleep between them so values are
    non-zero (mirrors how top samples CPU usage).
    """
    import psutil

    procs = _collect_procs(launchd_pid)
    if not procs:
        return []

    # First poll — seeds the interval counter, returns 0.0 (discard)
    for p in procs:
        try:
            p.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    time.sleep(0.2)

    results: list[ProcessInfo] = []
    for p in procs:
        try:
            with p.oneshot():
                name = p.name()
                cmdline: list[str] = p.cmdline() or []
                status = p.status()
                cpu = p.cpu_percent()
                mem_info = p.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                mem_pct = p.memory_percent()
                try:
                    num_fds = p.num_fds()
                except (psutil.AccessDenied, AttributeError):
                    num_fds = -1
                create_time = p.create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        results.append(
            ProcessInfo(
                pid=p.pid,
                name=name,
                role=_infer_role(cmdline),
                status=status,
                cpu_pct=round(cpu, 1),
                rss_mb=round(rss_mb, 1),
                mem_pct=round(mem_pct, 2),
                num_fds=num_fds,
                uptime=_format_uptime(create_time),
            )
        )

    return results
