"""Tests for rawspeak.history — HistoryStore and audio WAV saving."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from rawspeak.history import HistoryEntry, HistoryStore, _save_wav


class TestHistoryEntry:
    def test_default_audio_path_is_empty(self):
        entry = HistoryEntry(timestamp="1:00 PM", text="hello")
        assert entry.audio_path == ""

    def test_audio_path_can_be_set(self):
        entry = HistoryEntry(timestamp="1:00 PM", text="hello", audio_path="/tmp/x.wav")
        assert entry.audio_path == "/tmp/x.wav"


class TestHistoryStore:
    def test_append_returns_entry(self, tmp_path):
        store = HistoryStore(path=tmp_path / "history.jsonl")
        entry = store.append("hello world")
        assert entry.text == "hello world"
        assert entry.timestamp

    def test_append_saves_audio_path_when_audio_given(self, tmp_path):
        store = HistoryStore(path=tmp_path / "history.jsonl")
        audio = np.zeros(16000, dtype=np.float32)
        entry = store.append("hello", audio=audio, sample_rate=16000)
        assert entry.audio_path != ""
        assert entry.audio_path.endswith(".wav")
        assert Path(entry.audio_path).exists()

    def test_append_no_audio_path_when_no_audio(self, tmp_path):
        store = HistoryStore(path=tmp_path / "history.jsonl")
        entry = store.append("hello")
        assert entry.audio_path == ""

    def test_audio_path_persisted_in_jsonl(self, tmp_path):
        store = HistoryStore(path=tmp_path / "history.jsonl")
        audio = np.zeros(16000, dtype=np.float32)
        entry = store.append("hello", audio=audio, sample_rate=16000)

        line = (tmp_path / "history.jsonl").read_text().strip()
        payload = json.loads(line)
        assert payload["audio_path"] == entry.audio_path

    def test_list_recent_reads_audio_path(self, tmp_path):
        store = HistoryStore(path=tmp_path / "history.jsonl")
        audio = np.zeros(16000, dtype=np.float32)
        store.append("hello", audio=audio, sample_rate=16000)

        entries = store.list_recent()
        assert len(entries) == 1
        assert entries[0].audio_path.endswith(".wav")

    def test_list_recent_handles_missing_audio_path(self, tmp_path):
        """Old history entries without audio_path should still load."""
        hist_file = tmp_path / "history.jsonl"
        hist_file.write_text(
            json.dumps({"timestamp": "1:00 PM", "text": "old entry"}) + "\n"
        )
        store = HistoryStore(path=hist_file)
        entries = store.list_recent()
        assert len(entries) == 1
        assert entries[0].audio_path == ""

    def test_append_empty_text_does_not_write(self, tmp_path):
        hist_file = tmp_path / "history.jsonl"
        store = HistoryStore(path=hist_file)
        store.append("   ")
        assert not hist_file.exists()


class TestSaveWav:
    def test_creates_valid_wav_file(self, tmp_path):
        from datetime import datetime
        audio = np.linspace(-0.5, 0.5, 16000, dtype=np.float32)
        ts = datetime(2026, 1, 1, 12, 0, 0)

        # Temporarily redirect AUDIO_DIR to tmp_path
        import rawspeak.history as hist_mod
        original_audio_dir = hist_mod.AUDIO_DIR
        hist_mod.AUDIO_DIR = tmp_path
        try:
            path = _save_wav(audio, 16000, ts)
        finally:
            hist_mod.AUDIO_DIR = original_audio_dir

        assert path.exists()
        with wave.open(str(path)) as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == 16000

    def test_clips_audio_before_saving(self, tmp_path):
        """Audio values outside [-1, 1] must be clipped, not wrapped."""
        from datetime import datetime
        audio = np.array([2.0, -3.0, 0.5], dtype=np.float32)
        ts = datetime(2026, 1, 1, 12, 0, 0)

        import rawspeak.history as hist_mod
        original_audio_dir = hist_mod.AUDIO_DIR
        hist_mod.AUDIO_DIR = tmp_path
        try:
            path = _save_wav(audio, 16000, ts)
        finally:
            hist_mod.AUDIO_DIR = original_audio_dir

        with wave.open(str(path)) as wf:
            raw = wf.readframes(wf.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16)
        assert samples[0] == 32767   # 2.0 clipped to 1.0 → 32767
        assert samples[1] == -32767  # -3.0 clipped to -1.0 → -32767
