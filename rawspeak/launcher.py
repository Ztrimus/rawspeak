"""Install / uninstall rawspeak as a macOS LaunchAgent (auto-start at login)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_PLIST_LABEL = "com.rawspeak.agent"
_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_PLIST_LABEL}.plist"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{executable}</string>
    </array>

    <!-- Restart automatically if it crashes -->
    <key>KeepAlive</key>
    <true/>

    <!-- Start as soon as the user logs in -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Write stdout / stderr to ~/Library/Logs/rawspeak.log -->
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""


def _rawspeak_executable() -> str:
    """Return the absolute path to the rawspeak console script.

    Prefers the executable sitting next to the current Python interpreter
    (i.e. inside the active virtual-env's bin/) so the LaunchAgent uses the
    same environment that was set up with `pip install -e .`.
    """
    candidate = Path(sys.executable).parent / "rawspeak"
    if candidate.exists():
        return str(candidate)
    # Fall back to whatever is on PATH.
    found = shutil.which("rawspeak")
    if found:
        return found
    raise FileNotFoundError(
        "Could not locate the rawspeak executable. "
        "Make sure rawspeak is installed (`pip install -e .`) before running `rawspeak install`."
    )


def install() -> None:
    """Write a LaunchAgent plist and load it so rawspeak starts now and at every login."""
    if sys.platform != "darwin":
        print("Auto-start via LaunchAgent is only supported on macOS.")
        sys.exit(1)

    executable = _rawspeak_executable()
    log_path = Path.home() / "Library" / "Logs" / "rawspeak.log"

    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(
        _PLIST_TEMPLATE.format(
            label=_PLIST_LABEL,
            executable=executable,
            log=log_path,
        )
    )

    # Unload first in case a stale entry exists, then load the new one.
    subprocess.run(
        ["launchctl", "unload", str(_PLIST_PATH)],
        capture_output=True,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(_PLIST_PATH)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"launchctl load failed:\n{result.stderr.strip()}")
        sys.exit(1)

    print(f"rawspeak installed as a login item.")
    print(f"  Plist : {_PLIST_PATH}")
    print(f"  Log   : {log_path}")
    print(f"rawspeak is now running in the background — hotkey is active.")


def uninstall() -> None:
    """Unload and remove the LaunchAgent plist."""
    if sys.platform != "darwin":
        print("Auto-start via LaunchAgent is only supported on macOS.")
        sys.exit(1)

    if not _PLIST_PATH.exists():
        print("rawspeak is not installed as a login item.")
        return

    subprocess.run(
        ["launchctl", "unload", "-w", str(_PLIST_PATH)],
        capture_output=True,
    )
    _PLIST_PATH.unlink()
    print("rawspeak removed from login items and stopped.")
