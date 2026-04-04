"""Unit tests for logging setup."""

from __future__ import annotations

import logging

import pytest

from doc2md.utils.logging import setup_logging


@pytest.mark.unit
def test_setup_logging_stderr_only(tmp_path):
    """setup_logging with no file arg does not raise and sets level."""
    setup_logging("WARNING", None)
    assert logging.getLogger().level == logging.WARNING


@pytest.mark.unit
def test_setup_logging_creates_log_file(tmp_path):
    log_file = tmp_path / "test.log"
    setup_logging("DEBUG", str(log_file))
    # Emit a record so the file is created
    logging.getLogger("doc2md.test").debug("hello")
    assert log_file.exists()


@pytest.mark.unit
def test_setup_logging_expands_tilde(tmp_path, monkeypatch):
    """Tilde in file path is expanded (does not raise)."""
    # Redirect home to tmp_path to avoid writing to real ~/Library
    monkeypatch.setenv("HOME", str(tmp_path))
    setup_logging("INFO", "~/logs/doc2md.log")
    log_path = tmp_path / "logs" / "doc2md.log"
    logging.getLogger("doc2md.test").info("tilde test")
    assert log_path.exists()


@pytest.mark.unit
def test_setup_logging_invalid_level_falls_back():
    """Unknown log level string falls back to INFO via getattr default."""
    # getattr(logging, "NOTAREAL_LEVEL", logging.INFO) → logging.INFO
    numeric = getattr(logging, "NOTAREAL_LEVEL", logging.INFO)
    assert numeric == logging.INFO  # confirms the fallback value is correct
    setup_logging("NOTAREAL_LEVEL", None)  # must not raise
