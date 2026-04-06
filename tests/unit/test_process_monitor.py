"""Unit tests for the process_monitor utility."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from drop2md.utils.process_monitor import ProcessInfo, _format_uptime, _infer_role


# ── _infer_role ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_infer_role_watcher():
    assert _infer_role(["python3", "watch", "--config", "config.toml"]) == "watcher"


@pytest.mark.unit
def test_infer_role_converter():
    assert _infer_role(["python3", "convert", "file.pdf"]) == "converter"


@pytest.mark.unit
def test_infer_role_mcp_server_underscore():
    assert _infer_role(["python3", "-m", "drop2md.mcp_server"]) == "mcp-server"


@pytest.mark.unit
def test_infer_role_mcp_server_hyphen():
    assert _infer_role(["python3", "mcp-server"]) == "mcp-server"


@pytest.mark.unit
def test_infer_role_unknown():
    assert _infer_role(["python3", "status"]) == "unknown"


@pytest.mark.unit
def test_infer_role_empty_cmdline():
    assert _infer_role([]) == "unknown"


# ── _format_uptime ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_format_uptime_seconds():
    create_time = time.time() - 45
    assert _format_uptime(create_time) == "45s"


@pytest.mark.unit
def test_format_uptime_minutes():
    create_time = time.time() - (14 * 60 + 3)
    assert _format_uptime(create_time) == "14m 3s"


@pytest.mark.unit
def test_format_uptime_hours():
    create_time = time.time() - (2 * 3600 + 14 * 60)
    assert _format_uptime(create_time) == "2h 14m"


@pytest.mark.unit
def test_format_uptime_days():
    create_time = time.time() - (3 * 86400 + 7 * 3600)
    assert _format_uptime(create_time) == "3d 7h"


# ── ProcessInfo dataclass ────────────────────────────────────────────────────


@pytest.mark.unit
def test_process_info_fields():
    p = ProcessInfo(
        pid=1234,
        name="python3",
        role="watcher",
        status="running",
        cpu_pct=2.5,
        rss_mb=256.0,
        mem_pct=0.70,
        num_fds=12,
        uptime="1h 5m",
    )
    assert p.pid == 1234
    assert p.role == "watcher"
    assert p.uptime == "1h 5m"


# ── sample_processes (mocked _collect_procs) ─────────────────────────────────


@pytest.mark.unit
def test_sample_processes_empty_when_no_processes():
    """Returns empty list when _collect_procs finds nothing."""
    with patch("drop2md.utils.process_monitor._collect_procs", return_value=[]):
        with patch("drop2md.utils.process_monitor.time.sleep"):
            from drop2md.utils.process_monitor import sample_processes

            result = sample_processes(launchd_pid=None)
            assert result == []


@pytest.mark.unit
def test_sample_processes_handles_vanished_process():
    """Processes that vanish mid-sample (NoSuchProcess on oneshot) are silently skipped."""
    import psutil as real_psutil

    mock_proc = MagicMock()
    mock_proc.pid = 9999
    # cpu_percent baseline call is OK; the oneshot() context manager raises NoSuchProcess
    mock_proc.cpu_percent.return_value = 0.0
    mock_proc.oneshot.return_value.__enter__ = MagicMock(
        side_effect=real_psutil.NoSuchProcess(9999)
    )
    mock_proc.oneshot.return_value.__exit__ = MagicMock(return_value=False)

    with patch("drop2md.utils.process_monitor._collect_procs", return_value=[mock_proc]):
        with patch("drop2md.utils.process_monitor.time.sleep"):
            from drop2md.utils.process_monitor import sample_processes

            result = sample_processes(launchd_pid=None)
            assert result == []
