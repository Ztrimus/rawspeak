"""Configuration management for rawspeak."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

CONFIG_DIR = Path.home() / ".config" / "rawspeak"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG_TOML = """\
# rawspeak configuration
# Edit this file to customise rawspeak behaviour.

# Global hotkey to toggle recording (pynput format).
# Examples: "<ctrl>+<alt>+<space>", "<ctrl>+<shift>+r"
# Function keys work well as single-key triggers: "<f5>", "<f6>", etc.
# Note: Fn+<key> is not a distinct event on macOS — use a function key directly.
hotkey = "<ctrl>+<alt>+<space>"

# Optional mouse button that also toggles recording.
# Values: "middle" (scroll-wheel click), "x1", "x2", or "" to disable.
# "middle" = clicking the scroll wheel, which works as a convenient toggle.
mouse_button = "middle"

# Audio capture settings.
sample_rate = 16000  # Hz — Moonshine expects 16 kHz (resamples if different)
channels    = 1      # Mono

# Moonshine Voice model size for speech-to-text transcription.
# All models run fully local — no internet required after first download.
# Models are cached in ~/.cache/moonshine_voice after the first run.
#
# Options (accuracy improves, speed decreases top to bottom):
#   "tiny"             — 26 M params,  ~12.7% WER, fastest
#   "base"             — 58 M params,  ~10.1% WER, balanced CPU option
#   "small_streaming"  — 123 M params,  ~7.8% WER, good for mid-range hardware
#   "medium_streaming" — 245 M params,  ~6.7% WER, beats Whisper Large-v3
transcriber_model = "medium_streaming"

# Spoken language for transcription (ISO 639-1 code, e.g. "en").
# Supported: en, es, zh, ja, ko, vi, ar, uk
language = "en"

# Text-cleanup backend: "ollama" | "groq" | "none"
cleanup_backend = "ollama"

# Ollama settings (used when cleanup_backend = "ollama").
ollama_url   = "http://localhost:11434"
ollama_model = "llama3.2:3b"

# Groq settings (used when cleanup_backend = "groq").
# Set your key here or via the GROQ_API_KEY environment variable.
# groq_api_key = "gsk_..."
groq_model = "llama-3.1-8b-instant"

# Show a desktop notification after each successful paste.
show_notifications = true

# User glossary — teach RawSpeak proper nouns or words your STT engine
# consistently mishears.  Add one entry per line under [glossary]:
#   wrong_form = "correct form"
# Matching is whole-word and case-insensitive.
#
# [glossary]
# "Jhunjhun" = "Zinjad"
# "Suryabh"  = "Saurabh"
"""


@dataclass
class Config:
    # Hotkey
    hotkey: str = "<ctrl>+<alt>+<space>"
    mouse_button: str = "middle"  # scroll-wheel click; "" to disable

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    device: str | None = None  # None → system default

    # Transcription
    transcriber_model: str = "medium_streaming"
    language: str = "en"

    # Cleanup
    cleanup_backend: str = "ollama"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # UI
    show_notifications: bool = True

    # User glossary: correct words the STT engine mishears.
    # Populated from the [glossary] section of config.toml.
    user_glossary: dict[str, str] = field(default_factory=dict)


def load_config() -> Config:
    """Load configuration, merging file values on top of defaults."""
    config = Config()

    # Environment variable overrides.
    if api_key := os.environ.get("GROQ_API_KEY"):
        config.groq_api_key = api_key

    if not CONFIG_FILE.exists():
        return config

    try:
        with open(CONFIG_FILE, "rb") as fh:
            data = tomllib.load(fh)
        for key, value in data.items():
            if key == "glossary" and isinstance(value, dict):
                config.user_glossary = {str(k): str(v) for k, v in value.items()}
            elif hasattr(config, key):
                setattr(config, key, value)
    except Exception:
        pass  # silently use defaults if the file is malformed

    return config


def write_default_config() -> None:
    """Write a starter config file if none exists yet."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_TOML)
