"""Simple desktop UI that shows processed speech history."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional

from .history import HistoryEntry


class HistoryWindow:
    """Tiny Tkinter window showing timestamp + processed text rows."""

    def __init__(
        self,
        entries: Iterable[HistoryEntry],
        on_close: Optional[Callable[[], None]] = None,
        on_toggle_recording: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_close = on_close
        self._on_toggle_recording = on_toggle_recording
        self._queue: "queue.Queue[HistoryEntry]" = queue.Queue()

        self.root = tk.Tk()
        self.root.title("RawSpeak")
        self.root.geometry("860x520")
        self.root.minsize(640, 360)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(container, text="Processed speech", font=("Helvetica", 16, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            container,
            text="Newest items appear at the top.",
            foreground="#666666",
        )
        subtitle.pack(anchor="w", pady=(2, 6))

        self.notice_label = ttk.Label(
            container,
            text="",
            foreground="#666666",
        )
        self.notice_label.pack(anchor="w", pady=(0, 8))

        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=(0, 8))

        self.toggle_button = ttk.Button(
            controls,
            text="Start recording",
            command=self._handle_toggle,
        )
        self.toggle_button.pack(side=tk.LEFT)

        self.state_label = ttk.Label(
            controls,
            text="State: idle",
            foreground="#666666",
        )
        self.state_label.pack(side=tk.LEFT, padx=(12, 0))

        table_frame = ttk.Frame(container)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.table = ttk.Treeview(
            table_frame,
            columns=("time", "text"),
            show="headings",
        )
        self.table.heading("time", text="Time")
        self.table.heading("text", text="Text")
        self.table.column("time", width=110, anchor="w", stretch=False)
        self.table.column("text", anchor="w")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=yscroll.set)

        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        for entry in entries:
            self._insert(entry)

        self.root.after(250, self._drain_queue)

    def enqueue(self, entry: HistoryEntry) -> None:
        self._queue.put(entry)

    def set_state(self, state: str) -> None:
        if state == "listening":
            self.toggle_button.configure(text="Stop and process")
            self.state_label.configure(text="State: listening")
        elif state == "processing":
            self.toggle_button.configure(text="Processing...")
            self.state_label.configure(text="State: processing")
        else:
            self.toggle_button.configure(text="Start recording")
            self.state_label.configure(text="State: idle")

    def set_notice(self, message: str) -> None:
        self.notice_label.configure(text=message)

    def run_blocking(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        if self.root.winfo_exists():
            self.root.quit()
            self.root.destroy()

    def _insert(self, entry: HistoryEntry) -> None:
        if not entry.text:
            return
        self.table.insert("", 0, values=(entry.timestamp or "--", entry.text))

    def _drain_queue(self) -> None:
        while True:
            try:
                entry = self._queue.get_nowait()
            except queue.Empty:
                break
            self._insert(entry)
        if self.root.winfo_exists():
            self.root.after(250, self._drain_queue)

    def _handle_toggle(self) -> None:
        if self._on_toggle_recording is not None:
            self._on_toggle_recording()

    def _handle_close(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self.stop()
