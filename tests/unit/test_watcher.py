"""Unit tests for the folder watcher — debounce, queue, and file processing."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import FileCreatedEvent, FileMovedEvent

from drop2md.watcher import _DebounceHandler, _process_file, _worker

# ─── _DebounceHandler ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_debounce_enqueues_after_delay():
    """A created file is put on the queue after the debounce window."""
    q: queue.Queue[Path] = queue.Queue()
    handler = _DebounceHandler(q, debounce_seconds=0.05)

    handler.on_created(FileCreatedEvent("/tmp/report.pdf"))
    assert q.empty(), "Should not enqueue before debounce fires"

    time.sleep(0.15)
    assert not q.empty()
    assert q.get().name == "report.pdf"


@pytest.mark.unit
def test_debounce_resets_on_repeated_events():
    """Rapid repeated events for the same file reset the debounce timer."""
    q: queue.Queue[Path] = queue.Queue()
    handler = _DebounceHandler(q, debounce_seconds=0.1)

    for _ in range(5):
        handler.on_created(FileCreatedEvent("/tmp/chunk.pdf"))
        time.sleep(0.02)

    # Still within debounce window — should not be queued yet
    assert q.empty()

    time.sleep(0.2)
    # Should appear exactly once despite 5 events
    assert q.qsize() == 1


@pytest.mark.unit
def test_debounce_skips_ignored_extensions():
    """Files with ignored extensions (.md, .tmp, .lock) are never enqueued."""
    q: queue.Queue[Path] = queue.Queue()
    handler = _DebounceHandler(q, debounce_seconds=0.05)

    for name in ["output.md", "temp.tmp", "file.lock", ".hidden"]:
        handler.on_created(FileCreatedEvent(f"/tmp/{name}"))

    time.sleep(0.15)
    assert q.empty()


@pytest.mark.unit
def test_on_moved_enqueues_destination():
    """FileMovedEvent enqueues the destination path, not the source."""
    q: queue.Queue[Path] = queue.Queue()
    handler = _DebounceHandler(q, debounce_seconds=0.05)

    event = FileMovedEvent("/tmp/source.pdf", "/tmp/dest.pdf")
    handler.on_moved(event)

    time.sleep(0.15)
    assert not q.empty()
    assert q.get().name == "dest.pdf"


@pytest.mark.unit
def test_directory_events_ignored():
    """Directory creation events are not enqueued."""
    q: queue.Queue[Path] = queue.Queue()
    handler = _DebounceHandler(q, debounce_seconds=0.05)

    event = FileCreatedEvent("/tmp/newdir")
    event.is_directory = True
    handler.on_created(event)

    time.sleep(0.15)
    assert q.empty()


# ─── _process_file ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_process_file_writes_output(tmp_path):
    """_process_file converts an HTML file and writes the .md to output_dir."""
    html = tmp_path / "watch" / "test.html"
    html.parent.mkdir()
    html.write_text("<h1>Hello</h1><p>World</p>")

    out_dir = tmp_path / "output"
    out_dir.mkdir()

    cfg = MagicMock()
    cfg.paths.output_dir = out_dir
    cfg.output.overwrite = True
    cfg.output.add_frontmatter = False
    cfg.output.preserve_page_markers = False
    cfg.ollama.enabled = False

    _process_file(html, cfg)

    md_files = list(out_dir.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "Hello" in content


@pytest.mark.unit
def test_process_file_skips_missing_file(tmp_path):
    """_process_file silently skips files that no longer exist."""
    cfg = MagicMock()
    cfg.paths.output_dir = tmp_path
    cfg.output.overwrite = True

    # Should not raise
    _process_file(tmp_path / "ghost.pdf", cfg)


@pytest.mark.unit
def test_process_file_skips_when_overwrite_false(tmp_path):
    """_process_file skips conversion if output exists and overwrite=False."""
    html = tmp_path / "doc.html"
    html.write_text("<p>hi</p>")
    existing = tmp_path / "doc.md"
    existing.write_text("# already converted")

    cfg = MagicMock()
    cfg.paths.output_dir = tmp_path
    cfg.output.overwrite = False

    with patch("drop2md.watcher.dispatch") as mock_dispatch:
        _process_file(html, cfg)
    mock_dispatch.assert_not_called()


@pytest.mark.unit
def test_process_file_handles_conversion_error(tmp_path):
    """ConversionError during processing is caught and logged, not raised."""
    from drop2md.converters import ConversionError

    html = tmp_path / "bad.html"
    html.write_text("<p>hi</p>")

    cfg = MagicMock()
    cfg.paths.output_dir = tmp_path
    cfg.output.overwrite = True
    cfg.output.add_frontmatter = False
    cfg.output.preserve_page_markers = False
    cfg.ollama.enabled = False

    with patch("drop2md.watcher.dispatch", side_effect=ConversionError("boom")):
        _process_file(html, cfg)  # Must not raise


# ─── _worker ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_worker_processes_queued_files(tmp_path):
    """_worker pulls paths from the queue and calls _process_file for each."""
    q: queue.Queue[Path] = queue.Queue()
    stop = threading.Event()

    html = tmp_path / "a.html"
    html.write_text("<p>test</p>")
    q.put(html)

    processed: list[Path] = []

    def fake_process(path: Path, config: object) -> None:
        processed.append(path)

    cfg = MagicMock()

    t = threading.Thread(target=_worker, args=[q, cfg, stop], daemon=True)
    with patch("drop2md.watcher._process_file", side_effect=fake_process):
        t.start()
        q.join()
        stop.set()
        t.join(timeout=2)

    assert html in processed


@pytest.mark.unit
def test_worker_exits_on_stop_event(tmp_path):
    """_worker exits promptly when stop_event is set."""
    q: queue.Queue[Path] = queue.Queue()
    stop = threading.Event()
    cfg = MagicMock()

    t = threading.Thread(target=_worker, args=[q, cfg, stop], daemon=True)
    t.start()
    stop.set()
    t.join(timeout=2)
    assert not t.is_alive()
