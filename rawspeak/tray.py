"""System-tray icon using *pystray* + *Pillow*."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Colours for each application state.
_IDLE_COLOR = (80, 200, 80)        # green
_LISTENING_COLOR = (220, 60, 60)   # red
_PROCESSING_COLOR = (60, 140, 220) # blue

_ICON_SIZE = 64

_STATE_META = {
    "idle":       (_IDLE_COLOR,       "rawspeak — idle"),
    "listening":  (_LISTENING_COLOR,  "rawspeak — listening…"),
    "processing": (_PROCESSING_COLOR, "rawspeak — processing…"),
}


def _make_icon(color: tuple[int, int, int], size: int = _ICON_SIZE):
    """Return a *Pillow* ``Image`` containing a filled circle of *color*."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(*color, 255),
    )
    return img


class TrayApp:
    """Manages the system-tray icon and reacts to state changes.

    The tray runs in a daemon background thread so it never blocks the main
    application loop.
    """

    def __init__(self, on_quit: Optional[Callable[[], None]] = None) -> None:
        self.on_quit = on_quit
        self._icon = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the tray icon in a background daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True, name="rawspeak-tray")
        thread.start()

    def run_blocking(self) -> None:
        """Run the tray icon on the calling thread.

        Must be called from the main thread on macOS because AppKit
        (used by pystray's Darwin backend) does not permit NSWindow
        instantiation off the main thread.
        """
        self._run()

    def set_state(self, state: str) -> None:
        """Update the tray icon and tooltip to reflect *state*.

        Args:
            state: One of ``"idle"``, ``"listening"``, or ``"processing"``.
        """
        if self._icon is None:
            return
        color, title = _STATE_META.get(state, (_IDLE_COLOR, "rawspeak"))
        self._icon.icon = _make_icon(color)
        self._icon.title = title

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon is not None:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            import pystray
        except Exception as exc:
            logger.warning("pystray not available; tray icon disabled (%s)", exc)
            return

        menu = pystray.Menu(
            pystray.MenuItem("rawspeak", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

        self._icon = pystray.Icon(
            "rawspeak",
            _make_icon(_IDLE_COLOR),
            "rawspeak — idle",
            menu=menu,
        )
        self._icon.run()

    def _on_quit(self, icon, _item) -> None:
        icon.stop()
        if self.on_quit:
            self.on_quit()
