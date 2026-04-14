"""Configuration management for rawspeak."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Python 3.11+ includes tomllib in stdlib; older versions need tomli.
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]

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
sample_rate = 16000  # Hz — Whisper expects 16 kHz
channels    = 1      # Mono

# HuggingFace Whisper model identifier.
# Smaller = faster; larger = more accurate.
# Options: "openai/whisper-tiny", "openai/whisper-base", "openai/whisper-small"
whisper_model = "openai/whisper-base"

# Spoken language for transcription (ISO 639-1 code, e.g. "en").
# Forces Whisper to skip language detection and transcribe directly in this language,
# which is faster and avoids hallucination on background noise.
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
"""


@dataclass
class Config:
    # Hotkey
    hotkey: str = "<ctrl>+<alt>+<space>"
    mouse_button: str = "middle"  # scroll-wheel click; "" to disable

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    device: Optional[str] = None  # None → system default

    # Transcription
    whisper_model: str = "openai/whisper-base"
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


def load_config() -> Config:
    """Load configuration, merging file values on top of defaults."""
    config = Config()

    # Environment variable overrides.
    if api_key := os.environ.get("GROQ_API_KEY"):
        config.groq_api_key = api_key

    if not CONFIG_FILE.exists():
        return config

    if tomllib is None:
        return config

    try:
        with open(CONFIG_FILE, "rb") as fh:
            data = tomllib.load(fh)
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    except Exception:
        pass  # silently use defaults if the file is malformed

    return config


def write_default_config() -> None:
    """Write a starter config file if none exists yet."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_TOML)
