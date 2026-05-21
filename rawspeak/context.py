"""Runtime context helpers — active app detection and clipboard snapshot.

These are captured right before recording starts so the LLM cleaner knows:
- *which app* the cleaned text will be pasted into (to pick the right style)
- *what text* is already in that field (to match tone/continue a sentence)
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# App → category mapping
# ---------------------------------------------------------------------------

# Maps known app display-names to a semantic category.
# Matching is case-insensitive substring; first match wins.
_APP_CATEGORY_MAP: list[tuple[str, str]] = [
    # --- email ---
    ("Mail", "email"),
    ("Outlook", "email"),
    ("Superhuman", "email"),
    ("Mimestream", "email"),
    ("Spark", "email"),
    ("Airmail", "email"),
    ("Thunderbird", "email"),
    ("HEY", "email"),
    # --- work messaging ---
    ("Slack", "messaging"),
    ("Discord", "messaging"),
    ("Teams", "messaging"),
    ("Telegram", "messaging"),
    ("Signal", "messaging"),
    ("WhatsApp", "messaging"),
    ("Messages", "messaging"),
    # --- code / terminal ---
    ("Code", "code"),          # VS Code, Cursor (shows as "Code")
    ("Cursor", "code"),
    ("Windsurf", "code"),
    ("Xcode", "code"),
    ("PyCharm", "code"),
    ("IntelliJ", "code"),
    ("WebStorm", "code"),
    ("RubyMine", "code"),
    ("Sublime Text", "code"),
    ("Zed", "code"),
    ("vim", "code"),
    ("nvim", "code"),
    ("Terminal", "code"),
    ("iTerm", "code"),
    ("Warp", "code"),
    ("Ghostty", "code"),
    ("Alacritty", "code"),
    # --- notes / writing ---
    ("Notion", "notes"),
    ("Obsidian", "notes"),
    ("Bear", "notes"),
    ("Typora", "notes"),
    ("iA Writer", "notes"),
    ("Craft", "notes"),
    ("Ulysses", "notes"),
    ("Notes", "notes"),
    # --- browser ---
    ("Safari", "browser"),
    ("Chrome", "browser"),
    ("Firefox", "browser"),
    ("Arc", "browser"),
    ("Brave", "browser"),
    ("Edge", "browser"),
    ("Opera", "browser"),
]

# Human-readable style instruction injected into the LLM user turn.
STYLE_FOR_CATEGORY: dict[str, str] = {
    "email": (
        "Format for email: use full sentences, proper capitalisation, and "
        "complete punctuation. Be clear and professional."
    ),
    "messaging": (
        "Format for chat/messaging: keep it conversational. Contractions are "
        "fine. Lighter punctuation is OK. No need for formal sentence structure."
    ),
    "code": (
        "Format for a code editor or terminal: preserve technical terms, "
        "variable names, camelCase, snake_case, and CLI commands exactly as "
        "spoken. Avoid converting technical syntax into prose."
    ),
    "notes": (
        "Format for notes or a writing app: clean sentences, standard "
        "punctuation. Neither overly formal nor overly casual."
    ),
    "browser": (
        "Format as clear, well-punctuated text suitable for a web form or "
        "browser address bar."
    ),
}


def get_app_category(app_name: str) -> str:
    """Return the semantic category for *app_name*, or ``'other'``."""
    name_lower = app_name.lower()
    for fragment, category in _APP_CATEGORY_MAP:
        if fragment.lower() in name_lower:
            return category
    return "other"


# ---------------------------------------------------------------------------
# Active app detection
# ---------------------------------------------------------------------------

def get_active_app_name() -> str:
    """Return the display name of the frontmost application.

    Uses ``NSWorkspace`` on macOS (no special permissions required).
    Returns an empty string on other platforms or on any error.
    """
    if sys.platform != "darwin":
        return ""
    try:
        from AppKit import NSWorkspace  # type: ignore[import]

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return ""
        name = app.localizedName()
        return str(name) if name else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Clipboard snapshot
# ---------------------------------------------------------------------------

def get_clipboard_text(max_chars: int = 400) -> str:
    """Return the current clipboard text, capped at *max_chars*.

    Returns an empty string when the clipboard is empty, non-text, or on
    any error.  We cap the length to keep the LLM prompt compact.
    """
    try:
        import pyperclip  # already a rawspeak dependency

        text = pyperclip.paste()
        if isinstance(text, str) and text.strip():
            return text[:max_chars]
    except Exception:
        pass
    return ""
