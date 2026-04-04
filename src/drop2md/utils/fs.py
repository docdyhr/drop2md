"""File system utilities: atomic writes, safe filenames, processing locks."""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import TracebackType


def atomic_write(dest: Path, content: str) -> None:
    """Write *content* to *dest* atomically (write to .tmp, then rename).

    Prevents other processes (e.g. Claude Desktop) from reading a partial file.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def safe_filename(name: str, suffix: str = ".md") -> str:
    """Return a safe output filename derived from *name*.

    Replaces special characters with underscores, preserves alphanumerics,
    dots, hyphens, and spaces.
    """
    stem = Path(name).stem
    safe = re.sub(r"[^\w\s\-.]", "_", stem)
    safe = re.sub(r"[\s_]+", "_", safe).strip("_")
    return safe + suffix


class ProcessingLock:
    """Context manager that creates a .lock sidecar file to prevent double-processing.

    Usage::

        with ProcessingLock(path) as locked:
            if locked:
                process(path)
    """

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        self._lock_path = path.with_suffix(".lock")
        self._timeout = timeout
        self._acquired = False

    def __enter__(self) -> bool:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if not self._lock_path.exists():
                try:
                    self._lock_path.touch(exist_ok=False)
                    self._acquired = True
                    return True
                except FileExistsError:
                    pass
            time.sleep(0.1)
        return False

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._acquired:
            self._lock_path.unlink(missing_ok=True)
            self._acquired = False
