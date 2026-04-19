"""Main entry point — wires all components together."""

from __future__ import annotations

import logging
import sys
import threading

from .audio import AudioRecorder
from .cleaner import TextCleaner
from .config import load_config, write_default_config
from .history import HistoryStore
from .hotkey import HotkeyListener
from .paste import Paster
from .transcriber import Transcriber
from .tray import TrayApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class RawSpeak:
    """Orchestrates the full voice-to-text pipeline.

    State machine::

        idle  ──hotkey──►  listening  ──hotkey──►  processing  ──done──►  idle
    """

    def __init__(self, use_tk_ui: bool = True) -> None:
        self.config = load_config()
        write_default_config()
        self.use_tk_ui = use_tk_ui

        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            device=self.config.device,
        )
        self.transcriber = Transcriber(
            model_name=self.config.whisper_model,
            language=self.config.language,
        )
        self.cleaner = TextCleaner(
            backend=self.config.cleanup_backend,
            ollama_url=self.config.ollama_url,
            ollama_model=self.config.ollama_model,
            groq_api_key=self.config.groq_api_key,
            groq_model=self.config.groq_model,
        )
        self.paster = Paster()
        self.history = HistoryStore()
        self.ui = None
        if self.use_tk_ui:
            from .ui import HistoryWindow

            self.ui = HistoryWindow(
                entries=self.history.list_recent(),
                on_close=self._quit,
                on_toggle_recording=self._on_hotkey,
            )
        self.tray = TrayApp(on_quit=self._quit)
        self.hotkey = HotkeyListener(
            hotkey=self.config.hotkey,
            on_activate=self._on_hotkey,
            mouse_button=self.config.mouse_button,
        )

        self._recording = False
        self._processing = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Hotkey handler
    # ------------------------------------------------------------------

    def _on_hotkey(self) -> None:
        """Toggle recording on/off each time the hotkey fires."""
        with self._lock:
            if self._processing:
                return  # ignore while pipeline is running

            if not self._recording:
                self._start_recording()
            else:
                self._stop_and_process()

    def _start_recording(self) -> None:
        """Begin capturing audio (called with _lock held)."""
        try:
            self.recorder.start()
        except Exception:
            logger.exception("Failed to start audio recording")
            return
        self._recording = True
        logger.info("Recording started — press the hotkey again to stop")
        if self.ui:
            self.ui.set_state("listening")
        self.tray.set_state("listening")

    def _stop_and_process(self) -> None:
        """Stop recording and kick off the pipeline (called with _lock held)."""
        self._recording = False
        self._processing = True
        logger.info("Recording stopped — processing audio…")
        if self.ui:
            self.ui.set_state("processing")
        self.tray.set_state("processing")
        thread = threading.Thread(
            target=self._run_pipeline, daemon=True, name="rawspeak-pipeline"
        )
        thread.start()

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(self) -> None:
        """Transcribe → clean → paste.  Always resets state on exit."""
        try:
            audio = self.recorder.stop()

            duration = len(audio) / self.config.sample_rate
            if duration < 0.2:
                logger.info("Recording too short (%.2f s) — ignoring", duration)
                return

            logger.info("Transcribing %.1f s of audio…", duration)
            text = self.transcriber.transcribe(audio, self.config.sample_rate)
            logger.info("Raw transcription: %r", text)

            if not text.strip():
                logger.info("Empty transcription — nothing to paste")
                return

            logger.info("Cleaning up text…")
            cleaned = self.cleaner.clean(text)
            logger.info("Cleaned text: %r", cleaned)

            entry = self.history.append(cleaned)
            if self.ui:
                self.ui.enqueue(entry)

            logger.info("Pasting…")
            self.paster.paste(cleaned)
            logger.info("Done!")

        except Exception:
            logger.exception("Error in pipeline")
        finally:
            with self._lock:
                self._processing = False
            if self.ui:
                self.ui.set_state("idle")
            self.tray.set_state("idle")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _quit(self) -> None:
        """Cleanly shut down all components."""
        logger.info("Shutting down rawspeak")
        self._stop_event.set()
        if self.recorder.is_recording:
            self.recorder.stop()
        self.hotkey.stop()
        self.tray.stop()
        if self.ui:
            self.ui.stop()
        sys.exit(0)

    def run(self) -> None:
        """Start the application and block until the user quits."""
        logger.info(
            "rawspeak ready  |  hotkey: %s  |  model: %s  |  cleanup: %s",
            self.config.hotkey,
            self.config.whisper_model,
            self.config.cleanup_backend,
        )
        logger.info(
            "(The Whisper model will be downloaded on first use if not cached.)"
        )

        self._check_permissions()
        self.hotkey.start()

        # On macOS, pystray requires AppKit main-thread access and can clash
        # with alternative UI loops; keep tray disabled there for reliability.
        if sys.platform != "darwin":
            self.tray.start()

        if self.use_tk_ui and self.ui:
            try:
                self.ui.run_blocking()
            except KeyboardInterrupt:
                self._quit()
        else:
            try:
                self._stop_event.wait()
            except KeyboardInterrupt:
                self._quit()

    def _check_permissions(self) -> None:
        """Best-effort startup checks for required OS permissions."""
        if sys.platform != "darwin":
            return

        warnings: list[str] = []

        try:
            from ApplicationServices import (
                AXIsProcessTrusted,
                AXIsProcessTrustedWithOptions,
                kAXTrustedCheckOptionPrompt,
            )

            if not AXIsProcessTrusted():
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
                warnings.append("Enable Accessibility for RawSpeak/Terminal in System Settings.")
        except Exception:
            warnings.append("Accessibility permission status could not be verified.")

        try:
            from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess

            if not CGPreflightListenEventAccess():
                CGRequestListenEventAccess()
                warnings.append("Enable Input Monitoring for RawSpeak/Terminal in System Settings.")
        except Exception:
            warnings.append("Input Monitoring permission status could not be verified.")

        notice = (
            "Permissions check: "
            + (" ; ".join(warnings) if warnings else "looks good. Hotkey should work.")
        )
        if self.ui:
            self.ui.set_notice(notice)
        if warnings:
            logger.warning(notice)
        else:
            logger.info(notice)


def main() -> None:
    """CLI entry point installed by *pyproject.toml*.

    Subcommands
    -----------
    rawspeak             — run the app (default)
    rawspeak install     — install as a macOS login item (auto-start at login)
    rawspeak uninstall   — remove the login item
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="rawspeak",
        description="Local voice-to-text — hotkey to record, auto-paste cleaned text.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "run-headless", "install", "uninstall"],
        help="'install' sets up auto-start at login; 'uninstall' removes it.",
    )
    args = parser.parse_args()

    if args.command == "install":
        from .launcher import install

        install()
    elif args.command == "uninstall":
        from .launcher import uninstall

        uninstall()
    elif args.command == "run-headless":
        app = RawSpeak(use_tk_ui=False)
        app.run()
    else:
        # Default CLI run uses headless mode; desktop UI is now Electron.
        app = RawSpeak(use_tk_ui=False)
        app.run()


if __name__ == "__main__":
    main()
