"""Tests for rawspeak.launcher — install / uninstall helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rawspeak.launcher import (
    _PLIST_LABEL,
    _rawspeak_executable,
    install,
    uninstall,
)


class TestRawspeakExecutable:
    def test_returns_venv_bin_when_present(self, tmp_path):
        fake_exe = tmp_path / "rawspeak"
        fake_exe.touch()
        with patch("rawspeak.launcher.sys") as mock_sys:
            mock_sys.executable = str(tmp_path / "python")
            mock_sys.platform = "darwin"
            result = _rawspeak_executable()
        assert result == str(fake_exe)

    def test_falls_back_to_which(self, tmp_path):
        # No rawspeak next to interpreter → fall back to shutil.which
        with (
            patch("rawspeak.launcher.sys") as mock_sys,
            patch(
                "rawspeak.launcher.shutil.which", return_value="/usr/local/bin/rawspeak"
            ),
        ):
            mock_sys.executable = str(tmp_path / "python")
            result = _rawspeak_executable()
        assert result == "/usr/local/bin/rawspeak"

    def test_raises_when_not_found(self, tmp_path):
        with (
            patch("rawspeak.launcher.sys") as mock_sys,
            patch("rawspeak.launcher.shutil.which", return_value=None),
        ):
            mock_sys.executable = str(tmp_path / "python")
            with pytest.raises(FileNotFoundError):
                _rawspeak_executable()


class TestInstall:
    def test_writes_plist_and_calls_launchctl(self, tmp_path, monkeypatch):
        plist_path = tmp_path / f"{_PLIST_LABEL}.plist"
        log_path = tmp_path / "rawspeak.log"

        monkeypatch.setattr("rawspeak.launcher._PLIST_PATH", plist_path)
        monkeypatch.setattr("rawspeak.launcher.sys.platform", "darwin")

        mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        with (
            patch(
                "rawspeak.launcher._rawspeak_executable", return_value="/bin/rawspeak"
            ),
            patch("rawspeak.launcher.subprocess.run", mock_run),
            patch("rawspeak.launcher.Path.home", return_value=tmp_path),
        ):
            install()

        assert plist_path.exists()
        content = plist_path.read_text()
        assert "/bin/rawspeak" in content
        assert _PLIST_LABEL in content

    def test_exits_on_non_macos(self, monkeypatch):
        monkeypatch.setattr("rawspeak.launcher.sys.platform", "linux")
        with pytest.raises(SystemExit):
            install()


class TestUninstall:
    def test_removes_plist_and_calls_launchctl(self, tmp_path, monkeypatch):
        plist_path = tmp_path / f"{_PLIST_LABEL}.plist"
        plist_path.write_text("<plist/>")

        monkeypatch.setattr("rawspeak.launcher._PLIST_PATH", plist_path)
        monkeypatch.setattr("rawspeak.launcher.sys.platform", "darwin")

        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        with patch("rawspeak.launcher.subprocess.run", mock_run):
            uninstall()

        assert not plist_path.exists()
        mock_run.assert_called_once()

    def test_noop_when_not_installed(self, tmp_path, monkeypatch, capsys):
        plist_path = tmp_path / f"{_PLIST_LABEL}.plist"
        monkeypatch.setattr("rawspeak.launcher._PLIST_PATH", plist_path)
        monkeypatch.setattr("rawspeak.launcher.sys.platform", "darwin")

        uninstall()  # should not raise

        captured = capsys.readouterr()
        assert "not installed" in captured.out

    def test_exits_on_non_macos(self, monkeypatch):
        monkeypatch.setattr("rawspeak.launcher.sys.platform", "linux")
        with pytest.raises(SystemExit):
            uninstall()
