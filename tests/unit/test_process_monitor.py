"""Unit tests for the process_monitor utility."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from drop2md.utils.process_monitor import (
    ProcessInfo,
    _collect_procs,
    _format_uptime,
    _infer_role,
)

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
    with (
        patch("drop2md.utils.process_monitor._collect_procs", return_value=[]),
        patch("drop2md.utils.process_monitor.time.sleep"),
    ):
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

    with (
        patch("drop2md.utils.process_monitor._collect_procs", return_value=[mock_proc]),
        patch("drop2md.utils.process_monitor.time.sleep"),
    ):
        from drop2md.utils.process_monitor import sample_processes

        result = sample_processes(launchd_pid=None)
        assert result == []


@pytest.mark.unit
def test_sample_processes_returns_process_info():
    """sample_processes builds a ProcessInfo for each successfully sampled process."""
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.cpu_percent.return_value = 1.5
    mock_proc.name.return_value = "python3"
    mock_proc.cmdline.return_value = ["python3", "watch"]
    mock_proc.status.return_value = "running"
    mock_proc.memory_info.return_value = MagicMock(rss=256 * 1024 * 1024)
    mock_proc.memory_percent.return_value = 1.2
    mock_proc.num_fds.return_value = 15
    mock_proc.create_time.return_value = time.time() - 3600

    with (
        patch("drop2md.utils.process_monitor._collect_procs", return_value=[mock_proc]),
        patch("drop2md.utils.process_monitor.time.sleep"),
    ):
        from drop2md.utils.process_monitor import sample_processes

        result = sample_processes()

    assert len(result) == 1
    info = result[0]
    assert info.pid == 1234
    assert info.name == "python3"
    assert info.role == "watcher"
    assert info.cpu_pct == 1.5
    assert info.rss_mb == 256.0
    assert info.num_fds == 15


@pytest.mark.unit
def test_sample_processes_handles_no_fds_access_denied():
    """num_fds gracefully returns -1 when access is denied."""
    import psutil as real_psutil

    mock_proc = MagicMock()
    mock_proc.pid = 5678
    mock_proc.cpu_percent.return_value = 0.0
    mock_proc.name.return_value = "python3"
    mock_proc.cmdline.return_value = ["python3", "convert", "file.pdf"]
    mock_proc.status.return_value = "running"
    mock_proc.memory_info.return_value = MagicMock(rss=64 * 1024 * 1024)
    mock_proc.memory_percent.return_value = 0.5
    mock_proc.num_fds.side_effect = real_psutil.AccessDenied(5678)
    mock_proc.create_time.return_value = time.time() - 60

    with (
        patch("drop2md.utils.process_monitor._collect_procs", return_value=[mock_proc]),
        patch("drop2md.utils.process_monitor.time.sleep"),
    ):
        from drop2md.utils.process_monitor import sample_processes

        result = sample_processes()

    assert result[0].num_fds == -1


# ── _collect_procs ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_collect_procs_with_launchd_pid():
    """_collect_procs includes the launchd root process and its children."""

    mock_root = MagicMock()
    mock_root.pid = 100
    mock_child = MagicMock()
    mock_child.pid = 101
    mock_root.children.return_value = [mock_child]

    with patch("psutil.Process", return_value=mock_root):
        result = _collect_procs(launchd_pid=100)

    assert len(result) == 2


@pytest.mark.unit
def test_collect_procs_launchd_pid_not_found():
    """_collect_procs silently skips a launchd PID that no longer exists."""
    import psutil as real_psutil

    with (
        patch("psutil.Process", side_effect=real_psutil.NoSuchProcess(999)),
        patch("psutil.process_iter", return_value=[]),
    ):
        result = _collect_procs(launchd_pid=999)

    assert result == []


@pytest.mark.unit
def test_collect_procs_cmdline_scan():
    """_collect_procs finds drop2md processes via cmdline scan when no launchd PID given."""
    mock_proc = MagicMock()
    mock_proc.pid = 200
    mock_proc.info = {"cmdline": ["python3", "drop2md", "watch"]}

    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = _collect_procs(launchd_pid=None)

    assert mock_proc in result


@pytest.mark.unit
def test_collect_procs_skips_non_drop2md_processes():
    """_collect_procs ignores processes whose cmdline doesn't mention drop2md."""
    mock_proc = MagicMock()
    mock_proc.pid = 300
    mock_proc.info = {"cmdline": ["python3", "other_tool"]}

    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = _collect_procs(launchd_pid=None)

    assert result == []


@pytest.mark.unit
def test_collect_procs_handles_access_denied_in_cmdline():
    """_collect_procs silently skips processes that raise AccessDenied."""
    import psutil as real_psutil

    mock_proc = MagicMock()
    mock_proc.pid = 400
    mock_proc.info = MagicMock()
    mock_proc.info.__getitem__ = MagicMock(side_effect=real_psutil.AccessDenied(400))

    with patch("psutil.process_iter", return_value=[mock_proc]):
        result = _collect_procs(launchd_pid=None)

    assert result == []


@pytest.mark.unit
def test_collect_procs_handles_process_iter_error():
    """_collect_procs returns empty list if process_iter itself raises."""
    with patch("psutil.process_iter", side_effect=RuntimeError("iter failed")):
        result = _collect_procs(launchd_pid=None)

    assert result == []


@pytest.mark.unit
def test_sample_processes_first_poll_exception():
    """Processes raising NoSuchProcess during the first cpu_percent poll are skipped."""
    import psutil as real_psutil

    mock_proc = MagicMock()
    mock_proc.pid = 7777
    # First poll raises, second poll (inside oneshot) succeeds
    mock_proc.cpu_percent.side_effect = [
        real_psutil.NoSuchProcess(7777),
        1.0,
    ]
    mock_proc.name.return_value = "python3"
    mock_proc.cmdline.return_value = ["python3", "drop2md", "convert", "file.pdf"]
    mock_proc.status.return_value = "running"
    mock_proc.memory_info.return_value = MagicMock(rss=32 * 1024 * 1024)
    mock_proc.memory_percent.return_value = 0.3
    mock_proc.num_fds.return_value = 8
    mock_proc.create_time.return_value = time.time() - 120

    with (
        patch("drop2md.utils.process_monitor._collect_procs", return_value=[mock_proc]),
        patch("drop2md.utils.process_monitor.time.sleep"),
    ):
        from drop2md.utils.process_monitor import sample_processes

        result = sample_processes()

    # Process still appears — first poll exception is silent, second poll succeeds
    assert len(result) == 1
    assert result[0].role == "converter"
