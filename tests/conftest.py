"""Shared pytest fixtures for doc2md tests."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory that is cleaned up after each test."""
    return tmp_path


@pytest.fixture
def watch_dir(tmp_path: Path) -> Path:
    """A temporary watch directory."""
    d = tmp_path / "watch"
    d.mkdir()
    return d


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """A temporary output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def sample_pdf() -> Path:
    """Path to sample PDF fixture (created on first use if absent)."""
    path = FIXTURES_DIR / "sample.pdf"
    if not path.exists():
        pytest.skip("sample.pdf fixture not present")
    return path


@pytest.fixture
def sample_docx() -> Path:
    path = FIXTURES_DIR / "sample.docx"
    if not path.exists():
        pytest.skip("sample.docx fixture not present")
    return path


@pytest.fixture
def sample_html() -> Path:
    path = FIXTURES_DIR / "sample.html"
    if not path.exists():
        pytest.skip("sample.html fixture not present")
    return path


@pytest.fixture
def sample_png() -> Path:
    path = FIXTURES_DIR / "sample.png"
    if not path.exists():
        pytest.skip("sample.png fixture not present")
    return path
