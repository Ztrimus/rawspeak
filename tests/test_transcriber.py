"""Tests for rawspeak.transcriber — Transcriber and _resample."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from rawspeak.transcriber import Transcriber, _resample, _is_hallucination


class TestTranscriber:
    def test_empty_audio_returns_empty_string(self):
        t = Transcriber()
        assert t.transcribe(np.array([], dtype=np.float32)) == ""

    def test_calls_pipeline_with_correct_inputs(self):
        t = Transcriber(model_name="openai/whisper-base")
        mock_pipeline = MagicMock(return_value={"text": " hello world "})
        t._pipeline = mock_pipeline

        audio = np.zeros(16000, dtype=np.float32)
        result = t.transcribe(audio, sample_rate=16000)

        assert result == "hello world"
        call_args = mock_pipeline.call_args
        assert call_args[0][0]["sampling_rate"] == 16000
        assert len(call_args[0][0]["array"]) == 16000

    def test_passes_language_and_task_in_generate_kwargs(self):
        t = Transcriber(language="fr")
        t._pipeline = MagicMock(return_value={"text": "bonjour"})

        t.transcribe(np.zeros(16000, dtype=np.float32))

        _, kwargs = t._pipeline.call_args
        assert kwargs["generate_kwargs"]["language"] == "fr"
        assert kwargs["generate_kwargs"]["task"] == "transcribe"

    def test_hallucinated_output_returns_empty_string(self):
        t = Transcriber()
        # Simulate the "asa, asa, asa, ..." hallucination pattern
        hallucination = ", ".join(["asa"] * 50)
        t._pipeline = MagicMock(return_value={"text": hallucination})

        result = t.transcribe(np.zeros(16000, dtype=np.float32))

        assert result == ""

    def test_strips_whitespace_from_pipeline_output(self):
        t = Transcriber()
        t._pipeline = MagicMock(return_value={"text": "   padded text   "})
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "padded text"

    def test_handles_missing_text_key(self):
        t = Transcriber()
        t._pipeline = MagicMock(return_value={"chunks": []})
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_resamples_when_sample_rate_differs(self):
        t = Transcriber()
        received = {}

        def capture_pipeline(inputs, **kwargs):
            received.update(inputs)
            return {"text": "ok"}

        t._pipeline = capture_pipeline
        # 8 kHz audio → should be upsampled to 16 kHz before passing to pipeline
        audio_8k = np.ones(8000, dtype=np.float32)
        t.transcribe(audio_8k, sample_rate=8000)

        assert received["sampling_rate"] == 16000
        assert len(received["array"]) == 16000


class TestResample:
    def test_noop_when_rates_match(self):
        audio = np.arange(100, dtype=np.float32)
        result = _resample(audio, 16000, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_upsample_doubles_length(self):
        audio = np.ones(8000, dtype=np.float32)
        result = _resample(audio, 8000, 16000)
        assert len(result) == 16000

    def test_downsample_halves_length(self):
        audio = np.ones(16000, dtype=np.float32)
        result = _resample(audio, 16000, 8000)
        assert len(result) == 8000

    def test_output_dtype_is_float32(self):
        audio = np.ones(4000, dtype=np.float32)
        result = _resample(audio, 8000, 16000)
        assert result.dtype == np.float32


class TestIsHallucination:
    def test_asa_repetition_detected(self):
        text = ", ".join(["asa"] * 50)
        assert _is_hallucination(text) is True

    def test_normal_sentence_not_hallucination(self):
        assert _is_hallucination("I need to go to the store today") is False

    def test_short_text_not_hallucination(self):
        # Fewer than 8 words — never flagged regardless of repetition.
        assert _is_hallucination("asa asa asa asa") is False

    def test_slightly_repetitive_normal_not_flagged(self):
        # "the" appears 3/12 times = 25 % — below the 50 % threshold.
        text = "the cat sat on the mat and the dog ran to the park"
        assert _is_hallucination(text) is False

    def test_majority_single_token_flagged(self):
        # Word "blah" makes up 9/11 tokens — above threshold.
        text = "blah blah blah blah blah blah blah blah blah is fine"
        assert _is_hallucination(text) is True
