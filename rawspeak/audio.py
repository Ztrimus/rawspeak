"""Microphone audio recording using sounddevice."""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np


class AudioRecorder:
    """Records audio from the microphone.

    Usage::

        recorder = AudioRecorder()
        recorder.start()          # begin capturing
        audio = recorder.stop()   # returns float32 numpy array at *sample_rate* Hz
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: Optional[str] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

        self._chunks: list[np.ndarray] = []
        self._recording = False
        self._stream = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the audio stream and start capturing."""
        import sounddevice as sd

        self._chunks = []
        self._recording = True

        def _callback(indata: np.ndarray, frames: int, time: object, status: object) -> None:
            if self._recording:
                with self._lock:
                    self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            callback=_callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop capturing and return the recorded audio as a float32 array.

        Returns:
            1-D float32 numpy array of mono audio samples.
            Returns an empty array if nothing was recorded.
        """
        self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0)

        # Collapse multi-channel audio to mono.
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        return audio.astype(np.float32)

    @property
    def is_recording(self) -> bool:
        """True while the recorder is actively capturing."""
        return self._recording
