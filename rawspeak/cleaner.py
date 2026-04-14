"""LLM-based text cleanup for transcribed speech."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt sent to the LLM
# ---------------------------------------------------------------------------

_CLEANUP_PROMPT = (
    "Clean up the following transcribed speech. "
    "Remove filler words (um, uh, like, you know, sort of, kind of, basically, "
    "literally, actually when used as filler), fix grammar and punctuation, "
    "remove false starts and repetitions, and make the text read as clearly typed "
    "prose suitable for use as an AI prompt. Preserve the original meaning. "
    "Return ONLY the cleaned text — no explanation, no preamble.\n\n"
    "Transcription: {text}"
)


class TextCleaner:
    """Cleans up transcribed text using an LLM or a rule-based fallback.

    Backend priority:

    * ``"ollama"`` — calls a local Ollama server; falls back to rule-based on error.
    * ``"groq"``   — calls the Groq API;  falls back to rule-based on error.
    * ``"none"``   — rule-based only (no network requests).
    """

    def __init__(
        self,
        backend: str = "ollama",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.2:3b",
        groq_api_key: str = "",
        groq_model: str = "llama-3.1-8b-instant",
    ) -> None:
        self.backend = backend
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, text: str) -> str:
        """Return a cleaned version of *text*.

        Falls back to rule-based cleanup when the configured backend fails.
        """
        if not text.strip():
            return text

        if self.backend == "ollama":
            try:
                return self._clean_ollama(text)
            except Exception as exc:
                logger.warning("Ollama cleanup failed (%s); using rule-based fallback", exc)
                return _rule_based_clean(text)

        if self.backend == "groq":
            try:
                return self._clean_groq(text)
            except Exception as exc:
                logger.warning("Groq cleanup failed (%s); using rule-based fallback", exc)
                return _rule_based_clean(text)

        return _rule_based_clean(text)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _clean_ollama(self, text: str) -> str:
        """Send *text* to a local Ollama server and return the response."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": _CLEANUP_PROMPT.format(text=text),
            "stream": False,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        return result.get("response", text).strip()

    def _clean_groq(self, text: str) -> str:
        """Send *text* to the Groq chat-completions API and return the response."""
        if not self.groq_api_key:
            raise ValueError("Groq API key not configured")

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "user", "content": _CLEANUP_PROMPT.format(text=text)},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.groq_api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

# Filler patterns to remove unconditionally.
_FILLER_PATTERNS = [
    r"\bum+\b",
    r"\buh+\b",
    r"\byou\s+know\b",
    r"\bI\s+mean\b(?:,\s*)?",
]

_FILLER_RE = re.compile(
    "|".join(_FILLER_PATTERNS),
    flags=re.IGNORECASE,
)


def _rule_based_clean(text: str) -> str:
    """Remove common speech fillers and tidy whitespace."""
    result = _FILLER_RE.sub("", text)
    # Collapse multiple spaces.
    result = re.sub(r"\s{2,}", " ", result)
    # Remove spaces before punctuation.
    result = re.sub(r"\s+([.,!?;:])", r"\1", result)
    result = result.strip()
    # Capitalise the first character.
    if result:
        result = result[0].upper() + result[1:]
    return result
