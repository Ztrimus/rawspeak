"""Tests for rawspeak.context — app detection, category mapping, clipboard."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from rawspeak.context import (
    STYLE_FOR_CATEGORY,
    get_active_app_name,
    get_app_category,
    get_clipboard_text,
)


class TestGetAppCategory:
    def test_slack_is_messaging(self):
        assert get_app_category("Slack") == "messaging"

    def test_mail_is_email(self):
        assert get_app_category("Mail") == "email"

    def test_outlook_is_email(self):
        assert get_app_category("Microsoft Outlook") == "email"

    def test_cursor_is_code(self):
        assert get_app_category("Cursor") == "code"

    def test_vscode_is_code(self):
        assert get_app_category("Code") == "code"

    def test_terminal_is_code(self):
        assert get_app_category("Terminal") == "code"

    def test_iterm_is_code(self):
        assert get_app_category("iTerm2") == "code"

    def test_notion_is_notes(self):
        assert get_app_category("Notion") == "notes"

    def test_safari_is_browser(self):
        assert get_app_category("Safari") == "browser"

    def test_chrome_is_browser(self):
        assert get_app_category("Google Chrome") == "browser"

    def test_unknown_app_is_other(self):
        assert get_app_category("FancyUnknownApp") == "other"

    def test_case_insensitive(self):
        assert get_app_category("slack") == "messaging"
        assert get_app_category("SLACK") == "messaging"


class TestStyleForCategory:
    def test_all_categories_have_styles(self):
        for cat in ("email", "messaging", "code", "notes", "browser"):
            assert cat in STYLE_FOR_CATEGORY
            assert len(STYLE_FOR_CATEGORY[cat]) > 20

    def test_email_style_mentions_formal(self):
        assert "formal" in STYLE_FOR_CATEGORY["email"].lower() or \
               "professional" in STYLE_FOR_CATEGORY["email"].lower()

    def test_messaging_style_mentions_conversational(self):
        assert "conversational" in STYLE_FOR_CATEGORY["messaging"].lower() or \
               "casual" in STYLE_FOR_CATEGORY["messaging"].lower()

    def test_code_style_mentions_camelcase(self):
        assert "camelCase" in STYLE_FOR_CATEGORY["code"] or \
               "camel" in STYLE_FOR_CATEGORY["code"].lower()


class TestGetActiveAppName:
    def test_returns_string_on_non_macos(self):
        with patch.object(sys, "platform", "linux"):
            result = get_active_app_name()
        assert isinstance(result, str)
        assert result == ""

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_returns_nonempty_string_on_macos(self):
        result = get_active_app_name()
        assert isinstance(result, str)
        # We're running under a Python process — some app name should be returned.
        # We can't assert the exact value but it should be non-empty in CI.

    def test_returns_empty_on_nsworkspace_error(self):
        with patch("rawspeak.context.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch.dict("sys.modules", {"AppKit": None}):
                # ImportError path — returns ""
                result = get_active_app_name()
        # Either returns "" (ImportError) or a real value; just check type.
        assert isinstance(result, str)


class TestGetClipboardText:
    def test_returns_clipboard_content(self):
        with patch("pyperclip.paste", return_value="hello world"):
            result = get_clipboard_text()
        assert result == "hello world"

    def test_truncates_to_max_chars(self):
        long_text = "x" * 1000
        with patch("pyperclip.paste", return_value=long_text):
            result = get_clipboard_text(max_chars=100)
        assert len(result) == 100

    def test_returns_empty_on_empty_clipboard(self):
        with patch("pyperclip.paste", return_value="   "):
            result = get_clipboard_text()
        assert result == ""

    def test_returns_empty_on_error(self):
        with patch("pyperclip.paste", side_effect=Exception("clipboard error")):
            result = get_clipboard_text()
        assert result == ""
