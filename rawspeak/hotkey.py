"""Global hotkey listener using Quartz on macOS and pynput elsewhere."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

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
        self._mac_listener = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening for the hotkey (and optional mouse button) in daemon threads."""
        def _safe_activate() -> None:
            try:
                self.on_activate()
            except Exception:
                logger.exception("Unhandled error in hotkey callback")

        if sys.platform == "darwin":
            self._mac_listener = _MacHotkeyListener(self.hotkey, _safe_activate)
            self._mac_listener.start()
            logger.debug("macOS hotkey listener started for %r", self.hotkey)
        else:
            from pynput import keyboard

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
        if self._mac_listener is not None:
            self._mac_listener.stop()
            self._mac_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        logger.debug("Hotkey listener stopped")


class _MacHotkeyListener:
    """Quartz-based global key listener for macOS."""

    _KEYCODES = {
        "space": 49,
        "f1": 122,
        "f2": 120,
        "f3": 99,
        "f4": 118,
        "f5": 96,
        "f6": 97,
        "f7": 98,
        "f8": 100,
        "f9": 101,
        "f10": 109,
        "f11": 103,
        "f12": 111,
        "a": 0,
        "b": 11,
        "c": 8,
        "d": 2,
        "e": 14,
        "f": 3,
        "g": 5,
        "h": 4,
        "i": 34,
        "j": 38,
        "k": 40,
        "l": 37,
        "m": 46,
        "n": 45,
        "o": 31,
        "p": 35,
        "q": 12,
        "r": 15,
        "s": 1,
        "t": 17,
        "u": 32,
        "v": 9,
        "w": 13,
        "x": 7,
        "y": 16,
        "z": 6,
    }

    def __init__(self, hotkey: str, on_activate: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.on_activate = on_activate
        self._thread = None
        self._run_loop = None
        self._event_tap = None
        self._callback = None
        self._required_keycode, self._required_modifiers = self._parse_hotkey(hotkey)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="rawspeak-mac-hotkey")
        self._thread.start()

    def stop(self) -> None:
        if self._run_loop is None:
            return
        import Quartz

        Quartz.CFRunLoopStop(self._run_loop)
        if self._event_tap is not None:
            Quartz.CFMachPortInvalidate(self._event_tap)

    @classmethod
    def _parse_hotkey(cls, hotkey: str) -> tuple[int, int]:
        import Quartz

        modifier_map = {
            "ctrl": Quartz.kCGEventFlagMaskControl,
            "control": Quartz.kCGEventFlagMaskControl,
            "alt": Quartz.kCGEventFlagMaskAlternate,
            "option": Quartz.kCGEventFlagMaskAlternate,
            "shift": Quartz.kCGEventFlagMaskShift,
            "cmd": Quartz.kCGEventFlagMaskCommand,
            "command": Quartz.kCGEventFlagMaskCommand,
        }

        required_modifiers = 0
        required_keycode = None
        tokens = [t.strip().lower().strip("<>") for t in hotkey.split("+") if t.strip()]
        for token in tokens:
            if token in modifier_map:
                required_modifiers |= modifier_map[token]
            elif token in cls._KEYCODES:
                required_keycode = cls._KEYCODES[token]

        if required_keycode is None:
            raise ValueError(
                f"Unsupported hotkey {hotkey!r}. Use keys like <space>, <f5>, or letters."
            )
        return required_keycode, required_modifiers

    def _run(self) -> None:
        import Quartz

        def _callback(_proxy, event_type, event, _refcon):
            if event_type != Quartz.kCGEventKeyDown:
                return event

            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            flags = Quartz.CGEventGetFlags(event)
            if keycode == self._required_keycode and (flags & self._required_modifiers) == self._required_modifiers:
                try:
                    self.on_activate()
                except Exception:
                    logger.exception("Unhandled error in macOS hotkey callback")
            return event

        self._callback = _callback
        event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        self._event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            event_mask,
            self._callback,
            None,
        )
        if self._event_tap is None:
            logger.error("Failed to create macOS event tap for global hotkeys")
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, self._event_tap, 0)
        self._run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._run_loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._event_tap, True)
        Quartz.CFRunLoopRun()
