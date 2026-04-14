"""Global hotkey listener using *pynput*."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for a global hotkey combination and calls a callback on each activation.

    Optionally also listens for a mouse button (e.g. scroll-wheel / middle click)
    as an additional trigger.  The toggle logic (start/stop recording) is
    intentionally left to the caller so that this class stays a thin wrapper
    around *pynput*.
    """

    def __init__(
        self,
        hotkey: str,
        on_activate: Callable[[], None],
        mouse_button: str = "",
    ) -> None:
        """
        Args:
            hotkey: Hotkey string in pynput ``GlobalHotKeys`` format,
                    e.g. ``"<ctrl>+<alt>+<space>"``.
            on_activate: Called every time the hotkey fires.
            mouse_button: Optional pynput mouse button name that also triggers
                          the callback (e.g. ``"middle"``).  Empty string disables.
        """
        self.hotkey = hotkey
        self.on_activate = on_activate
        self.mouse_button = mouse_button
        self._listener = None
        self._mouse_listener = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening for the hotkey (and optional mouse button) in daemon threads."""
        from pynput import keyboard

        def _safe_activate() -> None:
            try:
                self.on_activate()
            except Exception:
                logger.exception("Unhandled error in hotkey callback")

        self._listener = keyboard.GlobalHotKeys({self.hotkey: _safe_activate})
        self._listener.start()
        logger.debug("Hotkey listener started for %r", self.hotkey)

        if self.mouse_button:
            self._start_mouse_listener(_safe_activate)

    def _start_mouse_listener(self, callback: Callable[[], None]) -> None:
        """Start a mouse listener that fires *callback* on the configured button press."""
        from pynput import mouse

        target_button = getattr(mouse.Button, self.mouse_button, None)
        if target_button is None:
            logger.warning(
                "Unknown mouse_button %r — mouse trigger disabled", self.mouse_button
            )
            return

        def _on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
            if pressed and button == target_button:
                callback()

        self._mouse_listener = mouse.Listener(on_click=_on_click)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()
        logger.debug("Mouse listener started for button %r", self.mouse_button)

    def stop(self) -> None:
        """Stop the hotkey and mouse listeners."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        logger.debug("Hotkey listener stopped")
