"""Tests for rawspeak.cleaner — TextCleaner and _rule_based_clean."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from rawspeak.cleaner import TextCleaner, _apply_glossary, _rule_based_clean


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

    def test_removes_consecutive_word_repetition(self):
        result = _rule_based_clean("I need to go For for tomorrow")
        assert "for for" not in result.lower()
        assert "tomorrow" in result.lower()

    def test_removes_double_sorry(self):
        result = _rule_based_clean("set an alarm for 1 a.m sorry sorry yes")
        assert "sorry sorry" not in result.lower()

    def test_three_word_repetition(self):
        result = _rule_based_clean("the the the store")
        assert "the the" not in result.lower()


class TestApplyGlossary:
    def test_replaces_exact_match(self):
        result = _apply_glossary("Hello Jhunjhun", {"Jhunjhun": "Zinjad"})
        assert result == "Hello Zinjad"

    def test_case_insensitive_match(self):
        result = _apply_glossary("Hello jhunjhun", {"Jhunjhun": "Zinjad"})
        assert "Zinjad" in result

    def test_whole_word_only(self):
        # Should not replace "Jhunjhuns" (different word form)
        result = _apply_glossary("Jhunjhuns party", {"Jhunjhun": "Zinjad"})
        assert "Jhunjhuns" in result

    def test_empty_glossary(self):
        assert _apply_glossary("hello world", {}) == "hello world"

    def test_multiple_entries(self):
        result = _apply_glossary(
            "Suryabh Jhunjhaj",
            {"Suryabh": "Saurabh", "Jhunjhaj": "Zinjad"},
        )
        assert result == "Saurabh Zinjad"


class TestBuildUserContent:
    def test_includes_date(self):
        import datetime
        cleaner = TextCleaner(backend="none")
        content = cleaner._build_user_content("hello")
        assert datetime.date.today().isoformat() in content

    def test_includes_transcription(self):
        cleaner = TextCleaner(backend="none")
        content = cleaner._build_user_content("test speech")
        assert "test speech" in content

    def test_includes_proper_nouns_from_glossary(self):
        cleaner = TextCleaner(backend="none", user_glossary={"Jhunjhun": "Zinjad"})
        content = cleaner._build_user_content("hello")
        assert "Zinjad" in content

    def test_no_glossary_omits_proper_noun_hint(self):
        cleaner = TextCleaner(backend="none")
        content = cleaner._build_user_content("hello")
        assert "Proper nouns" not in content



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

    def test_glossary_applied_before_rule_based(self):
        cleaner = TextCleaner(backend="none", user_glossary={"Jhunjhun": "Zinjad"})
        result = cleaner.clean("Hello Jhunjhun")
        assert "Jhunjhun" not in result
        assert "Zinjad" in result


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

    def test_ollama_payload_includes_system(self):
        """Ollama request must include the system prompt field."""
        cleaner = TextCleaner(backend="ollama")
        captured: list[dict] = []

        def fake_urlopen(req, timeout=30):
            captured.append(json.loads(req.data.decode()))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"response": "ok"}).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cleaner._clean_ollama("test input")

        assert "system" in captured[0]
        assert len(captured[0]["system"]) > 50  # non-trivial system prompt

    def test_ollama_payload_temperature(self):
        """Ollama request must set temperature=0.1 to prevent paraphrasing."""
        cleaner = TextCleaner(backend="ollama")
        captured: list[dict] = []

        def fake_urlopen(req, timeout=30):
            captured.append(json.loads(req.data.decode()))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"response": "ok"}).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cleaner._clean_ollama("test input")

        assert captured[0].get("options", {}).get("temperature") == 0.1

    def test_falls_back_to_rule_based_on_error(self):
        cleaner = TextCleaner(backend="ollama")

        with patch.object(cleaner, "_clean_ollama", side_effect=Exception("refused")):
            result = cleaner.clean("um this is a test")

        assert "um" not in result.lower()
        assert "test" in result.lower()

    def test_glossary_applied_before_llm_call(self):
        """Glossary substitution happens before the text is sent to Ollama."""
        cleaner = TextCleaner(backend="ollama", user_glossary={"Jhunjhun": "Zinjad"})
        sent_prompts: list[str] = []

        def fake_urlopen(req, timeout=30):
            payload = json.loads(req.data.decode())
            sent_prompts.append(payload.get("prompt", ""))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"response": "Hello Zinjad."}).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cleaner.clean("Hello Jhunjhun")

        assert "Jhunjhun" not in sent_prompts[0]
        assert "Zinjad" in sent_prompts[0]


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

    def test_groq_payload_has_system_role(self):
        """Groq request must include a system role message."""
        cleaner = TextCleaner(backend="groq", groq_api_key="test-key")
        captured: list[dict] = []

        def fake_urlopen(req, timeout=30):
            captured.append(json.loads(req.data.decode()))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}
            ).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cleaner._clean_groq("test input")

        roles = [m["role"] for m in captured[0]["messages"]]
        assert "system" in roles

    def test_groq_payload_temperature(self):
        """Groq request must set temperature=0.1."""
        cleaner = TextCleaner(backend="groq", groq_api_key="test-key")
        captured: list[dict] = []

        def fake_urlopen(req, timeout=30):
            captured.append(json.loads(req.data.decode()))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}
            ).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cleaner._clean_groq("test input")

        assert captured[0]["temperature"] == 0.1

    def test_falls_back_to_rule_based_on_error(self):
        cleaner = TextCleaner(backend="groq", groq_api_key="test-key")

        with patch.object(cleaner, "_clean_groq", side_effect=Exception("500")):
            result = cleaner.clean("um this is a test")

        assert "um" not in result.lower()
        assert "test" in result.lower()
