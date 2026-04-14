"""Tests for rawspeak.paste — Paster."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rawspeak.paste import Paster


class TestPasterPaste:
    def test_does_nothing_for_empty_text(self):
        paster = Paster()
        with patch.object(paster, "_set_clipboard") as mock_clip, \
             patch.object(paster, "_send_paste") as mock_paste:
            paster.paste("")
            paster.paste("   ")
        mock_clip.assert_not_called()
        mock_paste.assert_not_called()

    def test_sets_clipboard_then_pastes(self):
        paster = Paster(paste_delay=0)
        with patch.object(paster, "_set_clipboard") as mock_clip, \
             patch.object(paster, "_send_paste") as mock_paste:
            paster.paste("hello world")
        mock_clip.assert_called_once_with("hello world")
        mock_paste.assert_called_once()

    def test_paste_delay_is_respected(self):
        import time
        paster = Paster(paste_delay=0.05)
        with patch.object(paster, "_set_clipboard"), \
             patch.object(paster, "_send_paste"):
            start = time.monotonic()
            paster.paste("hi")
            elapsed = time.monotonic() - start
        assert elapsed >= 0.04


class TestPasterHelpers:
    def test_set_clipboard_calls_pyperclip(self):
        paster = Paster()
        with patch("pyperclip.copy") as mock_copy:
            paster._set_clipboard("test text")
        mock_copy.assert_called_once_with("test text")

    def test_send_paste_calls_pyautogui(self):
        paster = Paster()
        mock_pyautogui = MagicMock()
        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}):
            with patch("sys.platform", "linux"):
                paster._send_paste()
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")

    def test_send_paste_uses_command_v_on_macos(self):
        paster = Paster()
        mock_pyautogui = MagicMock()
        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}):
            with patch("sys.platform", "darwin"):
                paster._send_paste()
        mock_pyautogui.hotkey.assert_called_once_with("command", "v")
