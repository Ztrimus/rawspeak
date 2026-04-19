"""Persistent storage for processed speech entries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from .config import CONFIG_DIR

HISTORY_FILE = CONFIG_DIR / "history.jsonl"


@dataclass
class HistoryEntry:
    timestamp: str
    text: str


class HistoryStore:
    """Store and retrieve processed speech history as JSON lines."""

    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self.path = path

    def append(self, text: str) -> HistoryEntry:
        entry = HistoryEntry(
            timestamp=datetime.now().strftime("%I:%M %p").lstrip("0"),
            text=text.strip(),
        )
        if not entry.text:
            return entry

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
                    entries.append(HistoryEntry(timestamp=timestamp, text=text))
                except Exception:
                    continue

        if limit <= 0:
            return entries
        return entries[-limit:]
