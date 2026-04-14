"""Tests for rawspeak.cleaner — TextCleaner and _rule_based_clean."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from rawspeak.cleaner import TextCleaner, _rule_based_clean


class TestRuleBasedClean:
    def test_removes_um(self):
        assert "um" not in _rule_based_clean("um hello").lower()

    def test_removes_uh(self):
        assert "uh" not in _rule_based_clean("uh actually").lower()

    def test_removes_you_know(self):
        assert "you know" not in _rule_based_clean("you know what I mean").lower()

    def test_capitalises_first_letter(self):
        result = _rule_based_clean("hello world")
        assert result[0].isupper()

    def test_collapses_extra_spaces(self):
        result = _rule_based_clean("um  hello   world")
        assert "  " not in result

    def test_empty_string_returns_empty(self):
        assert _rule_based_clean("") == ""

    def test_preserves_meaningful_words(self):
        result = _rule_based_clean("I need to go to the store")
        assert "store" in result


class TestTextCleanerNoneBackend:
    def test_uses_rule_based(self):
        cleaner = TextCleaner(backend="none")
        result = cleaner.clean("um hello uh world")
        assert "um" not in result.lower()
        assert "uh" not in result.lower()
        assert "world" in result.lower()

    def test_blank_text_returned_unchanged(self):
        cleaner = TextCleaner(backend="none")
        assert cleaner.clean("") == ""
        assert cleaner.clean("   ") == "   "


class TestTextCleanerOllamaBackend:
    def test_returns_llm_response(self):
        cleaner = TextCleaner(backend="ollama")
        response_body = json.dumps({"response": "I need to go to the store."}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = cleaner._clean_ollama("um I need to go to the store")

        assert result == "I need to go to the store."

    def test_falls_back_to_rule_based_on_error(self):
        cleaner = TextCleaner(backend="ollama")

        with patch.object(cleaner, "_clean_ollama", side_effect=Exception("refused")):
            result = cleaner.clean("um this is a test")

        assert "um" not in result.lower()
        assert "test" in result.lower()


class TestTextCleanerGroqBackend:
    def test_raises_without_api_key(self):
        cleaner = TextCleaner(backend="groq", groq_api_key="")
        with pytest.raises(ValueError, match="API key"):
            cleaner._clean_groq("some text")

    def test_returns_llm_response(self):
        cleaner = TextCleaner(backend="groq", groq_api_key="test-key")
        response_body = json.dumps(
            {"choices": [{"message": {"content": "Cleaned text."}}]}
        ).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = cleaner._clean_groq("um some text uh here")

        assert result == "Cleaned text."

    def test_falls_back_to_rule_based_on_error(self):
        cleaner = TextCleaner(backend="groq", groq_api_key="test-key")

        with patch.object(cleaner, "_clean_groq", side_effect=Exception("500")):
            result = cleaner.clean("um this is a test")

        assert "um" not in result.lower()
        assert "test" in result.lower()
