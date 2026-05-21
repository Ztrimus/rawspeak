#!/usr/bin/env python3
"""Quick interactive test for the Moonshine STT engine.

Usage:
    .venv/bin/python scripts/test_stt.py

Steps:
    1. Press Enter to START recording
    2. Speak into your microphone
    3. Press Enter to STOP and transcribe
    4. See raw Moonshine output + timing
    5. Repeat as many times as you want — Ctrl+C to quit
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import sounddevice as sd

from rawspeak.transcriber import Transcriber

SAMPLE_RATE = 16_000
CHANNELS = 1

# ── Pre-load model once ───────────────────────────────────────────────────────
print("Loading Moonshine medium_streaming model… ", end="", flush=True)
t0 = time.perf_counter()
transcriber = Transcriber(model_size="medium_streaming", language="en")
transcriber._load_model()          # force eager load so timing is honest
load_ms = (time.perf_counter() - t0) * 1000
print(f"done ({load_ms:.0f} ms)\n")

# ── Interactive loop ──────────────────────────────────────────────────────────
round_num = 0
try:
    while True:
        round_num += 1
        print(f"─── Round {round_num} ───────────────────────────────")
        input("  Press Enter to START recording…")

        frames: list[np.ndarray] = []

        def _callback(indata, frame_count, time_info, status):
            frames.append(indata.copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=_callback,
        )

        with stream:
            print("  🎙  Recording — press Enter to STOP…")
            input()

        audio = np.concatenate(frames, axis=0).squeeze()
        duration = len(audio) / SAMPLE_RATE
        print(f"  Captured {duration:.1f}s of audio")

        if duration < 0.3:
            print("  Too short — skipping\n")
            continue

        print("  Transcribing… ", end="", flush=True)
        t0 = time.perf_counter()
        text = transcriber.transcribe(audio, sample_rate=SAMPLE_RATE)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        print(f"done ({elapsed_ms:.0f} ms)")
        print()
        if text:
            print(f"  Result : \"{text}\"")
        else:
            print("  Result : (empty — silence or hallucination filtered)")
        print()

except KeyboardInterrupt:
    print("\nDone.")
finally:
    transcriber.close()
