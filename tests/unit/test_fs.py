"""Unit tests for filesystem utilities."""

import pytest

from doc2md.utils.fs import ProcessingLock, atomic_write


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
    with ProcessingLock(path, timeout=0.2) as locked:
        assert locked is False
    # External lock should still be there
    assert lock_path.exists()
    lock_path.unlink()
