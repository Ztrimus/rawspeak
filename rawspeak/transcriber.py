"""Whisper transcription via HuggingFace *transformers*."""

from __future__ import annotations

import re

import numpy as np


class Transcriber:
    """Transcribes audio to text using a local Whisper model.

    The model is loaded lazily on the first call to :meth:`transcribe` so that
    startup time is kept low.
    """

    def __init__(
        self, model_name: str = "openai/whisper-base", language: str = "en"
    ) -> None:
        self.model_name = model_name
        self.language = language
        self._pipeline = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe *audio* to text.

        Args:
            audio: Float32 numpy array of audio samples.
            sample_rate: Sample rate of *audio* (Whisper expects 16 000 Hz).

        Returns:
            Transcribed text, stripped of leading/trailing whitespace.
        """
        if len(audio) == 0:
            return ""

        self._load_model()

        if sample_rate != 16000:
            audio = _resample(audio, sample_rate, 16000)

        result = self._pipeline(
            {"array": audio, "sampling_rate": 16000},
            return_timestamps=True,  # required for audio > 30 s; safe for shorter audio too
            generate_kwargs={"language": self.language, "task": "transcribe"},
        )
        text = result.get("text", "").strip()
        if _is_hallucination(text):
            return ""
        return text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the Whisper ASR pipeline."""
        if self._pipeline is not None:
            return

        import torch
        from transformers import pipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            device=device,
        )


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample *audio* from *orig_sr* to *target_sr*.

    Uses *resampy* when available, otherwise falls back to linear interpolation.
    """
    if orig_sr == target_sr:
        return audio

    try:
        import resampy  # type: ignore[import-untyped]

        return resampy.resample(audio, orig_sr, target_sr)
    except ImportError:
        pass

    # Naive fallback via linear interpolation.
    target_len = int(len(audio) * target_sr / orig_sr)
    indices = np.linspace(0, len(audio) - 1, target_len)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def _is_hallucination(text: str) -> bool:
    """Return True when the output is a repetitive Whisper hallucination.

    Whisper on multilingual models (or on silence/background noise) sometimes
    loops a single token thousands of times, e.g. ``"asa, asa, asa, ..."``.
    We detect this by checking whether a single word makes up more than half
    of all words in the output.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < 8:
        return False
    most_common_count = max(words.count(w) for w in set(words))
    return most_common_count / len(words) > 0.5
