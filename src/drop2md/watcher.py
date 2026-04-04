"""macOS folder watcher using watchdog FSEvents.

Monitors a drop directory and dispatches conversion jobs for new files.
Implements a 1-second debounce per path to handle files written in chunks.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from drop2md.config import Config
from drop2md.converters import ConversionError
from drop2md.dispatcher import dispatch
from drop2md.postprocess import postprocess
from drop2md.utils.fs import ProcessingLock, atomic_write, safe_filename

log = logging.getLogger(__name__)

# Extensions to silently ignore regardless of settings
_SKIP_EXTENSIONS = {".md", ".tmp", ".lock", ".log", ".part", ".crdownload"}


class _DebounceHandler(FileSystemEventHandler):
    """Watchdog event handler that debounces rapid file writes."""

    def __init__(self, file_queue: queue.Queue[Path], debounce_seconds: float = 1.0) -> None:
        super().__init__()
        self._queue = file_queue
        self._debounce = debounce_seconds
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, src_path: str) -> None:
        with self._lock:
            if src_path in self._timers:
                self._timers[src_path].cancel()
            timer = threading.Timer(
                self._debounce,
                self._enqueue,
                args=[src_path],
            )
            self._timers[src_path] = timer
            timer.start()

    def _enqueue(self, src_path: str) -> None:
        with self._lock:
            self._timers.pop(src_path, None)
        path = Path(src_path)
        if path.suffix.lower() not in _SKIP_EXTENSIONS and not path.name.startswith("."):
            log.debug("Enqueuing %s", path.name)
            self._queue.put(path)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._schedule(event.dest_path)


def _process_file(path: Path, config: Config) -> None:
    """Convert a single file and write output."""
    if not path.exists():
        log.debug("File gone before processing: %s", path)
        return

    output_dir = config.paths.output_dir
    out_filename = safe_filename(path.name)
    out_path = output_dir / out_filename

    if not config.output.overwrite and out_path.exists():
        log.info("Skipping %s (output exists, overwrite=false)", path.name)
        return

    with ProcessingLock(path) as locked:
        if not locked:
            log.warning("Could not acquire lock for %s — skipping", path.name)
            return

        try:
            log.info("Converting: %s", path.name)
            result = dispatch(path, output_dir)

            # Optional Ollama enhancement
            if config.ollama.enabled:
                try:
                    from drop2md.enhance import enhance

                    result = enhance(result, config)
                except Exception as exc:
                    log.warning("Ollama enhancement failed: %s", exc)

            md = postprocess(
                result,
                source=path,
                add_frontmatter=config.output.add_frontmatter,
                preserve_page_markers=config.output.preserve_page_markers,
            )
            atomic_write(out_path, md)
            log.info("Output: %s", out_path)
        except ConversionError as exc:
            log.error("Conversion failed for %s: %s", path.name, exc)
        except Exception as exc:
            log.exception("Unexpected error processing %s: %s", path.name, exc)


def _worker(file_queue: queue.Queue[Path], config: Config, stop_event: threading.Event) -> None:
    """Worker thread: pulls paths from queue and processes them."""
    while not stop_event.is_set():
        try:
            path = file_queue.get(timeout=1.0)
            _process_file(path, config)
            file_queue.task_done()
        except queue.Empty:
            continue


def run_watcher(config: Config) -> None:
    """Start the folder watcher. Blocks until KeyboardInterrupt or SIGTERM."""
    watch_dir = config.paths.watch_dir
    config.ensure_dirs()

    log.info("Watching: %s", watch_dir)
    log.info("Output:   %s", config.paths.output_dir)

    file_queue: queue.Queue[Path] = queue.Queue()
    stop_event = threading.Event()

    handler = _DebounceHandler(file_queue)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()

    worker_thread = threading.Thread(
        target=_worker,
        args=[file_queue, config, stop_event],
        daemon=True,
    )
    worker_thread.start()

    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
    finally:
        stop_event.set()
        observer.stop()
        observer.join()
        worker_thread.join(timeout=5)
        log.info("Watcher stopped.")
