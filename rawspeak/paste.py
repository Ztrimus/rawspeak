"""Clipboard injection and auto-paste into the active application."""

from __future__ import annotations

import time


class Paster:
    """Copies text to the clipboard then triggers a Ctrl+V paste."""

    def __init__(self, paste_delay: float = 0.1) -> None:
        """
        Args:
            paste_delay: Seconds to wait after writing the clipboard before
                         sending the paste keystroke.  A small delay is needed
                         so the target application has time to process the
                         clipboard write.
        """
        self.paste_delay = paste_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def paste(self, text: str) -> None:
        """Paste *text* into the currently focused application.

        Does nothing when *text* is blank.
        """
        if not text.strip():
            return

        self._set_clipboard(text)
        time.sleep(self.paste_delay)
        self._send_paste()

    # ------------------------------------------------------------------
    # Internal helpers (split out for easy mocking in tests)
    # ------------------------------------------------------------------

    def _set_clipboard(self, text: str) -> None:
        """Write *text* to the system clipboard."""
        import pyperclip

        pyperclip.copy(text)

    def _send_paste(self) -> None:
        """Send the platform-appropriate paste keystroke to the active window."""
        import sys

        import pyautogui

        if sys.platform == "darwin":
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")
