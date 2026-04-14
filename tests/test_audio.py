"""Tests for rawspeak.audio — AudioRecorder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rawspeak.audio import AudioRecorder


class TestAudioRecorderStop:
    def test_returns_empty_float32_when_no_chunks(self):
        recorder = AudioRecorder()
        result = recorder.stop()
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 0

    def test_concatenates_chunks(self):
        recorder = AudioRecorder(sample_rate=16000, channels=1)
        recorder._chunks = [
            np.ones((160, 1), dtype=np.float32),
            np.ones((160, 1), dtype=np.float32) * 0.5,
        ]
        result = recorder.stop()
        assert len(result) == 320
        assert result.dtype == np.float32

    def test_flattens_multichannel_to_mono(self):
        recorder = AudioRecorder(sample_rate=16000, channels=2)
        # Two-channel chunk: left=1, right=0  →  mean=0.5
        stereo = np.zeros((160, 2), dtype=np.float32)
        stereo[:, 0] = 1.0
        recorder._chunks = [stereo]
        result = recorder.stop()
        assert result.ndim == 1
        assert len(result) == 160
        np.testing.assert_allclose(result, 0.5)

    def test_stops_active_stream(self):
        recorder = AudioRecorder()
        mock_stream = MagicMock()
        recorder._stream = mock_stream
        recorder.stop()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert recorder._stream is None


class TestAudioRecorderIsRecording:
    def test_false_by_default(self):
        recorder = AudioRecorder()
        assert not recorder.is_recording

    def test_true_after_setting_flag(self):
        recorder = AudioRecorder()
        recorder._recording = True
        assert recorder.is_recording

    def test_false_after_stop(self):
        recorder = AudioRecorder()
        recorder._recording = True
        recorder.stop()
        assert not recorder.is_recording


class TestAudioRecorderStart:
    def _make_sd_mock(self):
        """Return (mock_sd_module, mock_stream_instance)."""
        mock_sd = MagicMock()
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        return mock_sd, mock_stream

    def test_start_opens_stream_and_sets_flag(self):
        recorder = AudioRecorder()
        mock_sd, mock_stream = self._make_sd_mock()

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            recorder.start()

        assert recorder._recording is True
        mock_sd.InputStream.assert_called_once()
        mock_stream.start.assert_called_once()

    def test_start_clears_previous_chunks(self):
        recorder = AudioRecorder()
        recorder._chunks = [np.ones(10, dtype=np.float32)]
        mock_sd, _ = self._make_sd_mock()

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            recorder.start()

        assert recorder._chunks == []
