"""LLM-based text cleanup for transcribed speech."""

from __future__ import annotations

import datetime
import json
import logging
import re
import urllib.error
import urllib.request

from .context import STYLE_FOR_CATEGORY, get_app_category

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts sent to the LLM
# ---------------------------------------------------------------------------

# System-level instructions — used as the ``system`` role for Groq and as the
# ``system`` field for Ollama /api/generate.
_SYSTEM_PROMPT = """\
The input you receive was captured by speech-to-text software and may contain \
STT-specific defects: mishearings, missing punctuation, run-on sentences, \
spoken self-corrections, filler words, and accidental repetitions.

Your job is to fix these defects and produce clean, professional text ready to \
send in an email, message, or chat — or for an AI agent to act on.

Rules:
1. Fix all grammar and spelling errors.
2. Add proper punctuation: commas, periods, apostrophes, and correct \
capitalisation for every sentence.
3. Remove filler words: um, uh, like, you know, basically, literally (when \
used as filler), sort of, kind of, I mean.
4. Handle spoken self-corrections: when the speaker corrects themselves \
("X sorry Y", "X sorry sorry Y", "X I mean Y", "X wait Y", "X no Y"), \
discard the error (X) and the correction marker, keep only the correction (Y).
5. Remove false starts and accidental word repetitions \
(e.g. "For for tomorrow" → "for tomorrow").
6. Fix context-obvious mishearings using surrounding words \
(e.g. "set all around for 1 a.m." → "set an alarm for 1 a.m.").
7. Apply spoken punctuation commands: if the speaker says "period", "comma", \
"new paragraph", "open quote", or "close quote", apply the punctuation and \
remove the command word from the output.
8. Preserve the original meaning exactly — do NOT add, remove, or reorder \
ideas. Do NOT summarise or paraphrase.
9. Output ONLY the cleaned text — no explanation, no preamble, no surrounding \
quotes.
10. If a section is too garbled to reconstruct confidently, output your best \
guess wrapped in [? ... ?] so the user knows to review it \
(e.g. "[? Study size 1 pm ?]" → the user will correct it manually).

Examples:

Input: "uh hello my name is john and I want to um schedule a meeting for \
monday I mean tuesday at 3 p.m"
Output: Hello, my name is John, and I want to schedule a meeting for Tuesday \
at 3 p.m.

Input: "I want to say to the alarm for 12 a.m sorry sorry 1 a.m I'm be ready \
For for tomorrow Yes."
Output: I want to set an alarm for 1 a.m. so I'll be ready for tomorrow.

Input: "yes it did not work but I'll try again I want to set all around for \
12 a.m sorry sorry one a.m and then I'm gonna do something else"
Output: Yes, it did not work, but I'll try again. I want to set an alarm for \
1 a.m., and then I'm going to do something else.\
"""


class TextCleaner:
    """Cleans up transcribed text using an LLM or a rule-based fallback.

    Backend priority:

    * ``"ollama"`` — calls a local Ollama server; falls back to rule-based on error.
    * ``"groq"``   — calls the Groq API;  falls back to rule-based on error.
    * ``"none"``   — rule-based only (no network requests).

    *user_glossary* maps STT-mangled strings to their correct form
    (e.g. ``{"Jhunjhun": "Zinjad"}``).  Substitutions are applied
    case-insensitively *before* the LLM call so the model never sees the
    garbled version.
    """

    def __init__(
        self,
        backend: str = "ollama",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.2:3b",
        groq_api_key: str = "",
        groq_model: str = "llama-3.1-8b-instant",
        user_glossary: dict[str, str] | None = None,
    ) -> None:
        self.backend = backend
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.user_glossary: dict[str, str] = user_glossary or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(
        self,
        text: str,
        active_app: str = "",
        clipboard_text: str = "",
    ) -> str:
        """Return a cleaned version of *text*.

        Args:
            text:           Raw STT transcription to clean.
            active_app:     Display name of the app the user is typing into
                            (e.g. "Slack", "Mail", "Cursor").  Used to pick
                            the right output style (casual vs formal vs code).
            clipboard_text: Text already in the focused field/clipboard before
                            recording started.  Gives the LLM context about
                            what the user is appending to.

        Applies the user glossary first, then calls the configured LLM
        backend.  Falls back to rule-based cleanup when the backend fails.
        """
        if not text.strip():
            return text

        text = _apply_glossary(text, self.user_glossary)

        if self.backend == "ollama":
            try:
                return self._clean_ollama(text, active_app, clipboard_text)
            except Exception as exc:
                logger.warning("Ollama cleanup failed (%s); using rule-based fallback", exc)
                return _rule_based_clean(text)

        if self.backend == "groq":
            try:
                return self._clean_groq(text, active_app, clipboard_text)
            except Exception as exc:
                logger.warning("Groq cleanup failed (%s); using rule-based fallback", exc)
                return _rule_based_clean(text)

        return _rule_based_clean(text)

    def _build_user_content(
        self,
        text: str,
        active_app: str = "",
        clipboard_text: str = "",
    ) -> str:
        """Build the user-turn message with runtime context hints.

        Injects:
        - Today's date (for resolving "tomorrow", "next Monday", etc.)
        - Active app name + per-app style instruction
        - Clipboard text (what the user is appending to)
        - Glossary proper nouns (so the LLM never normalises them away)
        """
        context_lines: list[str] = [
            f"Date: {datetime.date.today().isoformat()}",
        ]

        if active_app:
            context_lines.append(f"Active app: {active_app}")
            category = get_app_category(active_app)
            style = STYLE_FOR_CATEGORY.get(category, "")
            if style:
                context_lines.append(f"Output style: {style}")

        if clipboard_text:
            preview = clipboard_text[:300].replace("\n", " ").strip()
            context_lines.append(f"Text before cursor: \"{preview}\"")

        if self.user_glossary:
            names = ", ".join(sorted(self.user_glossary.values()))
            context_lines.append(
                f"Proper nouns to preserve (spell exactly as shown): {names}"
            )

        context_block = "Context:\n" + "\n".join(f"- {l}" for l in context_lines)
        return f"{context_block}\n\nRaw transcription:\n{text}"

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _clean_ollama(
        self,
        text: str,
        active_app: str = "",
        clipboard_text: str = "",
    ) -> str:
        """Send *text* to a local Ollama server and return the response."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "system": _SYSTEM_PROMPT,
            "prompt": self._build_user_content(text, active_app, clipboard_text),
            "stream": False,
            "options": {"temperature": 0.1},
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

    def _clean_groq(
        self,
        text: str,
        active_app: str = "",
        clipboard_text: str = "",
    ) -> str:
        """Send *text* to the Groq chat-completions API and return the response."""
        if not self.groq_api_key:
            raise ValueError("Groq API key not configured")

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_content(text, active_app, clipboard_text)},
            ],
            "temperature": 0.1,
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
# Glossary substitution
# ---------------------------------------------------------------------------


def _apply_glossary(text: str, glossary: dict[str, str]) -> str:
    """Replace STT-mangled tokens with their correct forms.

    Matching is whole-word and case-insensitive; replacement preserves
    the casing supplied in *glossary*.
    """
    for wrong, right in glossary.items():
        pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
        text = pattern.sub(right, text)
    return text


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

# Consecutive identical words: "For for" → "For", "the the" → "the".
_REPEAT_WORD_RE = re.compile(r"\b(\w+)(\s+\1)+\b", re.IGNORECASE)

# Spoken self-correction marker: "... sorry sorry" or lone trailing "sorry".
# Removes the marker; the LLM handles the preceding erroneous word.
_DOUBLE_SORRY_RE = re.compile(r"\bsorry\s+sorry\b", re.IGNORECASE)


def _rule_based_clean(text: str) -> str:
    """Remove common speech fillers and tidy whitespace."""
    result = _FILLER_RE.sub("", text)
    result = _DOUBLE_SORRY_RE.sub("", result)
    result = _REPEAT_WORD_RE.sub(r"\1", result)
    # Collapse multiple spaces.
    result = re.sub(r"\s{2,}", " ", result)
    # Remove spaces before punctuation.
    result = re.sub(r"\s+([.,!?;:])", r"\1", result)
    result = result.strip()
    # Capitalise the first character.
    if result:
        result = result[0].upper() + result[1:]
    return result
