"""Unit tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from drop2md.config import Config, OpenAIConfig, load_config


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
    monkeypatch.setenv("DROP2MD_WATCH_DIR", "/tmp/env_watch")
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.paths.watch_dir == Path("/tmp/env_watch")


@pytest.mark.unit
def test_env_override_ollama(monkeypatch, tmp_path):
    monkeypatch.setenv("DROP2MD_OLLAMA_ENABLED", "true")
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.ollama.enabled is True


@pytest.mark.unit
def test_ollama_provider_defaults_to_ollama(tmp_path):
    """provider field defaults to 'ollama' for backward compatibility."""
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.ollama.provider == "ollama"
    assert cfg.ollama.api_key == ""


@pytest.mark.unit
def test_env_override_enhance_provider(monkeypatch, tmp_path):
    """DROP2MD_ENHANCE_PROVIDER env var sets cfg.ollama.provider."""
    monkeypatch.setenv("DROP2MD_ENHANCE_PROVIDER", "gemini")
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.ollama.provider == "gemini"


@pytest.mark.unit
def test_openai_toml_section_parsed(tmp_path):
    """[openai] TOML section is parsed into cfg.openai."""
    toml = tmp_path / "test.toml"
    toml.write_text('[openai]\nmodel = "gpt-4o"\nbase_url = "https://example.com/v1"\n')
    cfg = load_config(toml)
    assert cfg.openai.model == "gpt-4o"
    assert cfg.openai.base_url == "https://example.com/v1"


@pytest.mark.unit
def test_legacy_claude_toml_section_ignored(tmp_path):
    """A legacy [claude] section (provider removed) still loads, and is ignored."""
    toml = tmp_path / "test.toml"
    toml.write_text('[claude]\nmodel = "claude-opus-4-6"\ntimeout_seconds = 60\n')
    cfg = load_config(toml)
    assert not hasattr(cfg, "claude")
    assert cfg.ollama.provider == "ollama"


@pytest.mark.unit
def test_backward_compat_no_new_sections(tmp_path):
    """Existing config.toml with no [openai] section loads without error."""
    toml = tmp_path / "test.toml"
    toml.write_text('[ollama]\nenabled = false\nmodel = "qwen3.5:latest"\n')
    cfg = load_config(toml)
    assert isinstance(cfg.openai, OpenAIConfig)
    assert cfg.ollama.provider == "ollama"  # default applied
