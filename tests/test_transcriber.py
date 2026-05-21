"""Tests for rawspeak.transcriber — Transcriber and _is_hallucination."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rawspeak.transcriber import Transcriber, _is_hallucination


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transcript(*texts: str) -> object:
    """Build a fake moonshine_voice Transcript with the given line texts."""
    lines = [SimpleNamespace(text=t) for t in texts]
    return SimpleNamespace(lines=lines)


def _transcriber_with_mock(mock_fn) -> Transcriber:
    """Return a Transcriber whose internal moonshine handle is pre-mocked."""
    t = Transcriber()
    mock_handle = MagicMock()
    mock_handle.transcribe_without_streaming.side_effect = mock_fn
    t._transcriber = mock_handle
    return t


# ---------------------------------------------------------------------------
# Transcriber
# ---------------------------------------------------------------------------

class TestTranscriber:
    def test_empty_audio_returns_empty_string(self):
        t = Transcriber()
        assert t.transcribe(np.array([], dtype=np.float32)) == ""

    def test_returns_joined_line_text(self):
        t = _transcriber_with_mock(
            lambda audio, sr: _make_transcript("Hello", "world")
        )
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "Hello world"

    def test_strips_whitespace(self):
        t = _transcriber_with_mock(
            lambda audio, sr: _make_transcript("  padded text  ")
        )
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "padded text"

    def test_single_line_transcript(self):
        t = _transcriber_with_mock(
            lambda audio, sr: _make_transcript("hello world")
        )
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "hello world"

    def test_empty_transcript_lines_returns_empty_string(self):
        t = _transcriber_with_mock(lambda audio, sr: _make_transcript())
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_hallucinated_output_returns_empty_string(self):
        hallucination = " ".join(["asa"] * 50)
        t = _transcriber_with_mock(
            lambda audio, sr: _make_transcript(hallucination)
        )
        result = t.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_passes_sample_rate_to_moonshine(self):
        received = {}

        def capture(audio, sr):
            received["sr"] = sr
            return _make_transcript("ok")

        t = _transcriber_with_mock(capture)
        t.transcribe(np.zeros(8000, dtype=np.float32), sample_rate=8000)
        assert received["sr"] == 8000

    def test_audio_converted_to_list_of_floats(self):
        received = {}

        def capture(audio, sr):
            received["audio"] = audio
            return _make_transcript("ok")

        t = _transcriber_with_mock(capture)
        t.transcribe(np.ones(100, dtype=np.float32))
        assert isinstance(received["audio"], list)
        assert all(isinstance(v, float) for v in received["audio"])

    def test_close_clears_internal_transcriber(self):
        t = Transcriber()
        mock_handle = MagicMock()
        t._transcriber = mock_handle
        t.close()
        mock_handle.close.assert_called_once()
        assert t._transcriber is None

    def test_close_is_safe_when_not_loaded(self):
        t = Transcriber()
        t.close()  # must not raise

    def test_load_model_uses_correct_arch(self):
        """_load_model maps the config string to the right ModelArch enum."""
        for model_size, arch_name in [
            ("tiny", "TINY"),
            ("base", "BASE"),
            ("small_streaming", "SMALL_STREAMING"),
            ("medium_streaming", "MEDIUM_STREAMING"),
        ]:
            t = Transcriber(model_size=model_size)

            fake_arch = SimpleNamespace(
                TINY="TINY",
                BASE="BASE",
                SMALL_STREAMING="SMALL_STREAMING",
                MEDIUM_STREAMING="MEDIUM_STREAMING",
            )
            fake_transcriber_cls = MagicMock(return_value=MagicMock())
            fake_get_model = MagicMock(return_value=("/fake/path", fake_arch.MEDIUM_STREAMING))

            with patch.dict(
                "sys.modules",
                {
                    "moonshine_voice": SimpleNamespace(
                        ModelArch=fake_arch,
                        Transcriber=fake_transcriber_cls,
                        get_model_for_language=fake_get_model,
                    )
                },
            ):
                t._load_model()

            call_kwargs = fake_transcriber_cls.call_args.kwargs
            assert call_kwargs["model_path"] == "/fake/path"
            assert call_kwargs["model_arch"] == arch_name

    def test_unknown_model_size_falls_back_to_medium_streaming(self):
        t = Transcriber(model_size="nonexistent_model")

        fake_arch = SimpleNamespace(
            TINY="TINY",
            BASE="BASE",
            SMALL_STREAMING="SMALL_STREAMING",
            MEDIUM_STREAMING="MEDIUM_STREAMING",
        )
        fake_transcriber_cls = MagicMock(return_value=MagicMock())
        fake_get_model = MagicMock(return_value=("/fake/path", None))

        with patch.dict(
            "sys.modules",
            {
                "moonshine_voice": SimpleNamespace(
                    ModelArch=fake_arch,
                    Transcriber=fake_transcriber_cls,
                    get_model_for_language=fake_get_model,
                )
            },
        ):
            t._load_model()

        call_kwargs = fake_transcriber_cls.call_args.kwargs
        assert call_kwargs["model_arch"] == "MEDIUM_STREAMING"


# ---------------------------------------------------------------------------
# _is_hallucination
# ---------------------------------------------------------------------------

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
        # "blah" makes up 9/11 tokens — above threshold.
        text = "blah blah blah blah blah blah blah blah blah is fine"
        assert _is_hallucination(text) is True
