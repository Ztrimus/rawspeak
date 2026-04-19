"""Headless backend entrypoint for Electron packaging."""

from rawspeak.main import RawSpeak


if __name__ == "__main__":
    RawSpeak(use_tk_ui=False).run()
