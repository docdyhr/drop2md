"""Unit tests for filesystem utilities."""

from unittest.mock import patch

import pytest

from drop2md.utils.fs import ProcessingLock, atomic_write


@pytest.mark.unit
def test_atomic_write_creates_file(tmp_path):
    dest = tmp_path / "output.md"
    atomic_write(dest, "# Hello\n")
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "# Hello\n"


@pytest.mark.unit
def test_atomic_write_creates_parent_dirs(tmp_path):
    dest = tmp_path / "subdir" / "nested" / "file.md"
    atomic_write(dest, "content")
    assert dest.exists()


@pytest.mark.unit
def test_atomic_write_no_tmp_left_over(tmp_path):
    dest = tmp_path / "output.md"
    atomic_write(dest, "content")
    tmp = dest.with_suffix(".tmp")
    assert not tmp.exists()


@pytest.mark.unit
def test_atomic_write_overwrites(tmp_path):
    dest = tmp_path / "output.md"
    atomic_write(dest, "original")
    atomic_write(dest, "updated")
    assert dest.read_text(encoding="utf-8") == "updated"


@pytest.mark.unit
def test_processing_lock_acquired(tmp_path):
    path = tmp_path / "file.pdf"
    path.touch()
    with ProcessingLock(path) as locked:
        assert locked is True
        assert (tmp_path / "file.lock").exists()
    assert not (tmp_path / "file.lock").exists()


@pytest.mark.unit
def test_processing_lock_prevents_double_processing(tmp_path):
    path = tmp_path / "file.pdf"
    path.touch()
    lock_path = path.with_suffix(".lock")
    lock_path.touch()  # Simulate existing lock
    try:
        with ProcessingLock(path, timeout=0.2) as locked:
            assert locked is False
        # External lock should still be there — we don't own it
        assert lock_path.exists()
    finally:
        lock_path.unlink(missing_ok=True)


@pytest.mark.unit
def test_atomic_write_cleans_up_tmp_on_failure(tmp_path):
    """atomic_write removes the .tmp file and re-raises when writing fails."""
    dest = tmp_path / "output.md"
    with (
        patch("pathlib.Path.rename", side_effect=OSError("rename failed")),
        pytest.raises(OSError, match="rename failed"),
    ):
        atomic_write(dest, "content")
    tmp = dest.with_suffix(".tmp")
    assert not tmp.exists()


@pytest.mark.unit
def test_processing_lock_file_exists_error(tmp_path):
    """ProcessingLock handles FileExistsError race condition gracefully."""
    path = tmp_path / "race.pdf"
    path.touch()

    call_count = 0

    original_touch = path.with_suffix(".lock").__class__.touch

    def mock_touch(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FileExistsError("lock exists")
        # Second call succeeds (simulates the race condition resolving)
        return original_touch(self, *args, **kwargs)

    with (
        patch.object(type(path.with_suffix(".lock")), "touch", mock_touch),
        ProcessingLock(path, timeout=1.0) as locked,
    ):
        assert locked is True
