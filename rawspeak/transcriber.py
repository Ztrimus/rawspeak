"""Moonshine Voice speech-to-text transcription."""

from __future__ import annotations

import re

import numpy as np


class Transcriber:
    """Transcribes audio to text using Moonshine Voice.

    The model is loaded lazily on the first call to :meth:`transcribe` so that
    startup time is kept low.

    Model size options (``model_size`` constructor arg):

    +-----------------------+------------+----------+-----------------------------+
    | model_size            | Params     | WER      | Notes                       |
    +=======================+============+==========+=============================+
    | ``tiny``              | 26 M       | ~12.7 %  | Fastest, lowest accuracy    |
    | ``base``              | 58 M       | ~10.1 %  | Balanced CPU option         |
    | ``small_streaming``   | 123 M      | ~7.8 %   | Good for mid-range hardware |
    | ``medium_streaming``  | 245 M      | ~6.7 %   | **Default** — best accuracy |
    +-----------------------+------------+----------+-----------------------------+

    Moonshine Medium Streaming beats Whisper Large-v3 (7.4 % WER) at 1/6 the
    parameters and completes in ~107 ms on Apple Silicon.
    """

    def __init__(
        self, model_size: str = "medium_streaming", language: str = "en"
    ) -> None:
        self.model_size = model_size
        self.language = language
        self._transcriber = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe *audio* to text.

        Args:
            audio: Float32 numpy array of mono audio samples in [-1.0, 1.0].
            sample_rate: Sample rate of *audio*. Moonshine resamples internally
                so any rate is accepted; 16 kHz avoids the resample overhead.

        Returns:
            Transcribed text, stripped of leading/trailing whitespace.
            Returns an empty string for silent or empty audio.
        """
        if len(audio) == 0:
            return ""

        self._load_model()

        # Moonshine Voice expects a plain Python list of float32 values.
        audio_list = audio.astype(np.float32).tolist()

        transcript = self._transcriber.transcribe_without_streaming(
            audio_list, sample_rate
        )
        text = " ".join(line.text for line in transcript.lines).strip()

        if _is_hallucination(text):
            return ""

        return text

    def close(self) -> None:
        """Release Moonshine model resources."""
        if self._transcriber is not None:
            self._transcriber.close()
            self._transcriber = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the Moonshine transcriber (downloads model on first use)."""
        if self._transcriber is not None:
            return

        from moonshine_voice import (  # type: ignore[import-untyped]
            ModelArch,
            Transcriber as _MoonshineTranscriber,
            get_model_for_language,
        )

        _ARCH_MAP: dict[str, object] = {
            "tiny": ModelArch.TINY,
            "base": ModelArch.BASE,
            "small_streaming": ModelArch.SMALL_STREAMING,
            "medium_streaming": ModelArch.MEDIUM_STREAMING,
        }

        # Downloads and caches the model under ~/.cache/moonshine_voice on
        # first run; subsequent calls are instant (cache hit).
        model_path, _ = get_model_for_language(self.language)
        model_arch = _ARCH_MAP.get(self.model_size, ModelArch.MEDIUM_STREAMING)

        self._transcriber = _MoonshineTranscriber(
            model_path=model_path,
            model_arch=model_arch,
        )


def _is_hallucination(text: str) -> bool:
    """Return True when output appears to be a repetitive hallucination.

    Checks whether a single word accounts for more than half of all words.
    This catches looping artefacts where the model emits the same token
    hundreds of times instead of real speech content.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < 8:
        return False
    most_common_count = max(words.count(w) for w in set(words))
    return most_common_count / len(words) > 0.5
