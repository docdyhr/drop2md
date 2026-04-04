"""Unit tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from doc2md.config import Config, load_config


@pytest.mark.unit
def test_load_config_defaults_when_no_file(tmp_path):
    missing = tmp_path / "nonexistent.toml"
    cfg = load_config(missing)
    assert isinstance(cfg, Config)
    assert cfg.pdf.use_marker is True
    assert cfg.ollama.enabled is False


@pytest.mark.unit
def test_load_config_from_toml(tmp_path):
    toml = tmp_path / "test.toml"
    toml.write_text(
        '[paths]\nwatch_dir = "/tmp/watch"\noutput_dir = "/tmp/out"\n'
        '[ollama]\nenabled = true\nmodel = "llava:latest"\n'
    )
    cfg = load_config(toml)
    assert cfg.paths.watch_dir == Path("/tmp/watch")
    assert cfg.ollama.enabled is True
    assert cfg.ollama.model == "llava:latest"


@pytest.mark.unit
def test_load_config_expands_tilde(tmp_path):
    toml = tmp_path / "test.toml"
    toml.write_text('[paths]\nwatch_dir = "~/drop"\noutput_dir = "~/out"\n')
    cfg = load_config(toml)
    assert not str(cfg.paths.watch_dir).startswith("~")


@pytest.mark.unit
def test_env_override_watch_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC2MD_WATCH_DIR", "/tmp/env_watch")
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.paths.watch_dir == Path("/tmp/env_watch")


@pytest.mark.unit
def test_env_override_ollama(monkeypatch, tmp_path):
    monkeypatch.setenv("DOC2MD_OLLAMA_ENABLED", "true")
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.ollama.enabled is True
