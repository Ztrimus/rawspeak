# rawspeak

Even if you speak messy, it understands you and writes it cleanly — optimized for AI prompts.

A free, privacy-first local voice-to-text desktop tool.  
Press a hotkey → record your voice → get clean, ready-to-paste text.

---

## Features

| Feature | Details |
|---|---|
| **Global hotkey toggle** | Press once to start recording, press again to stop |
| **Local Whisper transcription** | Runs entirely on your machine via HuggingFace `transformers` |
| **LLM text cleanup** | Removes filler words, fixes grammar, reformats for AI prompts |
| **Auto-paste** | Injects the cleaned text into whatever app is currently focused |
| **System tray icon** | Green = idle · Red = listening · Blue = processing |
| **100 % offline** | Optionally uses Groq free tier for cleanup; everything else is local |

---

## Quick start

### 1. Install system dependencies

**macOS**
```bash
brew install portaudio
```

**Ubuntu / Debian**
```bash
sudo apt install portaudio19-dev python3-tk
```

**Windows** — PortAudio ships with the `sounddevice` wheel; no extra step needed.

### 2. Install rawspeak

```bash
pip install rawspeak
```

Or install from source:

```bash
git clone https://github.com/uopx-engineering/rawspeak
cd rawspeak
pip install -e .
```

### 3. (Optional) Install a local LLM via Ollama

```bash
# macOS / Linux
curl https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

rawspeak talks to Ollama automatically.  
If Ollama isn't running, cleanup falls back to a fast rule-based pass.

### 4. Run

```bash
rawspeak
```

A tray icon appears. Press **Ctrl + Alt + Space** to toggle recording.

### 5. macOS first launch (Gatekeeper + permissions)

If you install the DMG build, macOS may show:
"Apple could not verify 'RawSpeak' is free of malware..."

This is expected for unsigned/not-notarized MVP builds.

1. Drag `RawSpeak.app` to `Applications`.
2. In Finder, open `Applications`, right-click `RawSpeak`, then click `Open`.
3. If still blocked, go to `System Settings -> Privacy & Security` and click `Open Anyway` for RawSpeak.

After launch, grant required permissions:

- `System Settings -> Privacy & Security -> Microphone` -> enable `RawSpeak`
- `System Settings -> Privacy & Security -> Accessibility` -> enable `RawSpeak`
- `System Settings -> Privacy & Security -> Input Monitoring` -> enable `RawSpeak`

Without these permissions, hotkeys, recording, or paste automation may fail.

---

## Configuration

On first run rawspeak writes a config file at:

- **Linux/macOS:** `~/.config/rawspeak/config.toml`
- **Windows:** `%USERPROFILE%\.config\rawspeak\config.toml`

```toml
# Global hotkey to toggle recording.
hotkey = "<ctrl>+<alt>+<space>"

# Whisper model (tiny < base < small — smaller = faster).
whisper_model = "openai/whisper-base"

# Cleanup backend: "ollama" | "groq" | "none"
cleanup_backend = "ollama"

# Ollama (local LLM)
ollama_url   = "http://localhost:11434"
ollama_model = "llama3.2:3b"

# Groq (free cloud API — set GROQ_API_KEY env var or add key here)
# groq_api_key = "gsk_..."
groq_model = "llama-3.1-8b-instant"
```

### Groq API key

```bash
export GROQ_API_KEY="gsk_..."
rawspeak
```

Or set `groq_api_key` in the config file and set `cleanup_backend = "groq"`.

---

## Architecture

```
hotkey press
    │
    ▼
AudioRecorder          (sounddevice — 16 kHz mono float32)
    │  audio array
    ▼
Transcriber            (HuggingFace transformers + openai/whisper-base)
    │  raw text
    ▼
TextCleaner            (Ollama → Groq → rule-based fallback)
    │  cleaned text
    ▼
Paster                 (pyperclip clipboard + pyautogui Ctrl+V)
    │
    ▼
active application
```

### Module overview

| Module | Responsibility |
|---|---|
| `rawspeak/config.py` | TOML config + environment-variable overrides |
| `rawspeak/audio.py` | Microphone capture (`AudioRecorder`) |
| `rawspeak/transcriber.py` | Whisper ASR (`Transcriber`) |
| `rawspeak/cleaner.py` | LLM / rule-based cleanup (`TextCleaner`) |
| `rawspeak/paste.py` | Clipboard injection + Ctrl+V (`Paster`) |
| `rawspeak/hotkey.py` | Global hotkey listener (`HotkeyListener`) |
| `rawspeak/tray.py` | System-tray icon (`TrayApp`) |
| `rawspeak/main.py` | Orchestrator + CLI entry point (`RawSpeak`) |

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

---

## Roadmap (post-v1)

- [ ] macOS paste via `pbpaste` / accessibility API
- [ ] Voice shortcuts
- [ ] Personal vocabulary / dictionary
- [ ] Multi-language support
- [ ] GPU acceleration flag in config
