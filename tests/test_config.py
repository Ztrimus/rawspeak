"""Tests for rawspeak.config — Config and load_config."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from rawspeak.config import Config, load_config, write_default_config


class TestConfigDefaults:
    def test_default_hotkey(self):
        assert Config().hotkey == "<ctrl>+<alt>+<space>"

    def test_default_sample_rate(self):
        assert Config().sample_rate == 16000

    def test_default_transcriber_model(self):
        assert Config().transcriber_model == "medium_streaming"

    def test_default_cleanup_backend(self):
        assert Config().cleanup_backend == "ollama"


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", tmp_path / "nonexistent.toml")
        config = load_config()
        assert isinstance(config, Config)
        assert config.sample_rate == 16000

    def test_env_variable_sets_groq_api_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env-key-123")
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", tmp_path / "nonexistent.toml")
        config = load_config()
        assert config.groq_api_key == "env-key-123"

    def test_loads_values_from_toml_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('transcriber_model = "small_streaming"\nsample_rate = 8000\n')
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", cfg_file)
        config = load_config()
        assert config.transcriber_model == "small_streaming"
        assert config.sample_rate == 8000

    def test_ignores_unknown_keys_in_toml(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('nonexistent_key = "value"\n')
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", cfg_file)
        config = load_config()  # should not raise
        assert isinstance(config, Config)

    def test_returns_defaults_on_malformed_toml(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_bytes(b"\xff\xfe invalid toml !!!")
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", cfg_file)
        config = load_config()
        assert config.sample_rate == 16000


class TestWriteDefaultConfig:
    def test_creates_file_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rawspeak.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", tmp_path / "config.toml")
        write_default_config()
        assert (tmp_path / "config.toml").exists()

    def test_does_not_overwrite_existing_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("existing = true\n")
        monkeypatch.setattr("rawspeak.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("rawspeak.config.CONFIG_FILE", cfg_file)
        write_default_config()
        assert cfg_file.read_text() == "existing = true\n"
