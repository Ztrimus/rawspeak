"""Persistent storage for processed speech entries."""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np

from .config import CONFIG_DIR

HISTORY_FILE = CONFIG_DIR / "history.jsonl"
AUDIO_DIR = CONFIG_DIR / "audio"


@dataclass
class HistoryEntry:
    timestamp: str
    text: str
    audio_path: str = field(default="")


class HistoryStore:
    """Store and retrieve processed speech history as JSON lines.

    Each entry can optionally reference a WAV file saved alongside the
    text — useful for self-diagnosing STT quality issues (play back the
    raw audio to hear exactly what the model received).
    """

    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self.path = path

    def append(self, text: str, audio: np.ndarray | None = None, sample_rate: int = 16000) -> HistoryEntry:
        """Persist *text* and an optional raw *audio* recording.

        When *audio* is provided it is saved as a 16-bit PCM WAV file under
        ``~/.config/rawspeak/audio/`` using a timestamp-based filename.
        """
        ts = datetime.now()
        entry = HistoryEntry(
            timestamp=ts.strftime("%I:%M %p").lstrip("0"),
            text=text.strip(),
        )
        if not entry.text:
            return entry

        if audio is not None and len(audio) > 0:
            try:
                audio_path = _save_wav(audio, sample_rate, ts)
                entry.audio_path = str(audio_path)
            except Exception:
                pass  # audio saving is best-effort; don't break the pipeline

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
        return entry

    def list_recent(self, limit: int = 300) -> List[HistoryEntry]:
        if not self.path.exists():
            return []

        entries: List[HistoryEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    text = str(payload.get("text", "")).strip()
                    timestamp = str(payload.get("timestamp", "")).strip()
                    if not text:
                        continue
                    entries.append(HistoryEntry(
                        timestamp=timestamp,
                        text=text,
                        audio_path=str(payload.get("audio_path", "")),
                    ))
                except Exception:
                    continue

        if limit <= 0:
            return entries
        return entries[-limit:]


# ---------------------------------------------------------------------------
# WAV helpers
# ---------------------------------------------------------------------------

def _save_wav(audio: np.ndarray, sample_rate: int, ts: datetime) -> Path:
    """Write *audio* as a 16-bit mono PCM WAV and return the path."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = ts.strftime("%Y%m%d_%H%M%S") + ".wav"
    path = AUDIO_DIR / filename

    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return path
