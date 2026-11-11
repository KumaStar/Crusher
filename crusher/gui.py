"""Desktop UI (CustomTkinter) - Windows / macOS / Linux."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from . import engines
from .core import (APP_NAME, IS_WIN, KIND_LABELS, KINDS, MB, MISSING_FFMPEG_MSG, Cancelled, Info,
                   Job, Result, find_tool, fmt_size, fmt_time, save_config)
from .engines.video import PRESETS

RES_CHOICES = ["auto", "1080", "720", "540", "480", "360"]
ICON = Path(__file__).resolve().parent.parent / "crusher.ico"
RED = ("#c0392b", "#ff6b6b")
GREEN = ("#1e8449", "#58d68d")
NEEDS_FFMPEG = {"video", "audio", "gif"}


def reveal(path: str) -> None:
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


def set_icon(win) -> None:
    if IS_WIN and ICON.is_file():
        try:
            win.iconbitmap(str(ICON))
        except Exception:  # noqa: BLE001
            pass


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, cfg: dict, on_save):
        super().__init__(master)
        self.cfg, self.on_save = cfg, on_save
        self.title("Crusher – Settings")
        self.resizable(False, False)
        self.transient(master)
        self.after(250, lambda: set_icon(self))
        pad = {"padx": 12, "pady": 4}

        ctk.CTkLabel(self, text="Default target size (MB)", font=ctk.CTkFont(weight="bold")
                     ).grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(12, 2))
        self.targets = {}
        for i, k in enumerate(KINDS):
            r, c = 1 + i // 2, (i % 2) * 2
            ctk.CTkLabel(self, text=KIND_LABELS[k], anchor="w").grid(row=r, column=c, sticky="w", **pad)
            e = ctk.CTkEntry(self, width=70, justify="right")
            e.insert(0, f"{cfg['targets'][k]:g}")
            e.grid(row=r, column=c + 1, sticky="w", **pad)
            self.targets[k] = e

        r0 = 2 + len(KINDS) // 2
        ctk.CTkLabel(self, text="General", font=ctk.CTkFont(weight="bold")
                     ).grid(row=r0, column=0, columnspan=4, sticky="w", padx=12, pady=(12, 2))

        def row(r, text):
            ctk.CTkLabel(self, text=text, anchor="w").grid(row=r, column=0, sticky="w", **pad)

        row(r0 + 1, "Video max resolution")
        self.res = ctk.CTkOptionMenu(self, values=[x if x == "auto" else x + "p" for x in RES_CHOICES], width=110)
        cur = str(cfg["max_height"])
        self.res.set(cur if cur == "auto" else cur + "p")
        self.res.grid(row=r0 + 1, column=1, columnspan=3, sticky="w", **pad)

        row(r0 + 2, "Video speed preset")
        self.preset = ctk.CTkOptionMenu(self, values=PRESETS, width=110)
        self.preset.set(cfg["x264_preset"])
        self.preset.grid(row=r0 + 2, column=1, columnspan=3, sticky="w", **pad)

        row(r0 + 3, "File name suffix")
        self.suffix = ctk.CTkEntry(self, width=140)
        self.suffix.insert(0, cfg["suffix"])
        self.suffix.grid(row=r0 + 3, column=1, columnspan=3, sticky="w", **pad)

        row(r0 + 4, "Output folder")
        self.outdir = ctk.CTkEntry(self, width=240, placeholder_text="Same folder as source")
        if cfg["output_dir"]:
            self.outdir.insert(0, cfg["output_dir"])
        self.outdir.grid(row=r0 + 4, column=1, columnspan=2, sticky="we", **pad)
        ctk.CTkButton(self, text="…", width=32, command=lambda: self._pick(self.outdir)
                      ).grid(row=r0 + 4, column=3, padx=(0, 12))

        row(r0 + 5, "FFmpeg folder")
        self.ffdir = ctk.CTkEntry(self, width=240, placeholder_text="Auto-detect")
        if cfg["ffmpeg_path"]:
            self.ffdir.insert(0, cfg["ffmpeg_path"])
        self.ffdir.grid(row=r0 + 5, column=1, columnspan=2, sticky="we", **pad)
        ctk.CTkButton(self, text="…", width=32, command=lambda: self._pick(self.ffdir)
                      ).grid(row=r0 + 5, column=3, padx=(0, 12))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=r0 + 6, column=0, columnspan=4, sticky="e", padx=12, pady=(12, 12))
        ctk.CTkButton(bar, text="Cancel", width=90, fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=self.destroy).pack(side="right")
        ctk.CTkButton(bar, text="Save", width=90, command=self._save).pack(side="right", padx=8)
        self.after(150, self._focus)

    def _focus(self):
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def _pick(self, entry):
        d = filedialog.askdirectory(parent=self)
        if d:
            entry.delete(0, "end")
            entry.insert(0, os.path.normpath(d))

    def _save(self):
        targets = {}
        for k, e in self.targets.items():
            try:
                t = float(e.get().replace(",", "."))
                if not 0.01 <= t <= 100000:
                    raise ValueError
                targets[k] = t
            except ValueError:
                messagebox.showerror("Settings", f"{KIND_LABELS[k]} target must be a number of MB.", parent=self)
                return
        out_dir = self.outdir.get().strip()
        if out_dir and not os.path.isdir(out_dir):
            messagebox.showerror("Settings", "Output folder doesn't exist.", parent=self)
            return
        self.cfg.update(targets=targets, max_height=self.res.get().rstrip("p"),
                        x264_preset=self.preset.get(), suffix=self.suffix.get().strip() or "_crushed",
                        output_dir=out_dir, ffmpeg_path=self.ffdir.get().strip())
        save_config(self.cfg)
        self.on_save()
        self.destroy()


class DoneDialog(ctk.CTkToplevel):
    def __init__(self, master, r: Result, target_mb: float):
        super().__init__(master)
        self.title("Crusher – Done")
        self.resizable(False, False)
        self.transient(master)
        self.after(250, lambda: set_icon(self))
        saved = 100 * (1 - r.out_size / r.src_size) if r.src_size else 0
        head = "⚠  Best effort" if r.missed else "✔  Crushed!"
        ctk.CTkLabel(self, text=head, font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=RED if r.missed else ("gray10", "gray90")).pack(padx=24, pady=(18, 4))
        ctk.CTkLabel(self, text=f"{fmt_size(r.src_size)}  →  {fmt_size(r.out_size)}   (−{saved:.0f}%)",
                     font=ctk.CTkFont(size=14)).pack(padx=24)
        if r.missed:
            ctk.CTkLabel(self, text=f"Couldn't reach {target_mb:g} MB – this is the smallest it gets.",
                         text_color=RED).pack(padx=24)
        ctk.CTkLabel(self, text=f"{r.detail} · took {fmt_time(r.elapsed)}", text_color="gray"
                     ).pack(padx=24, pady=(2, 0))
        ctk.CTkLabel(self, text=Path(r.out).name, text_color="gray", wraplength=360).pack(padx=24, pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(pady=(0, 16))
        ctk.CTkButton(bar, text="Show file", width=110, command=lambda: (reveal(r.out), self.destroy())
                      ).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="OK", width=90, command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(150, lambda: (self.lift(), self.focus_force()))


class App(ctk.CTk):
    def __init__(self, cfg: dict, initial: str | None = None, auto: bool = False,
                 target_override: float | None = None):
        super().__init__()
        self.cfg = cfg
        self.target_override = target_override
        self.title(APP_NAME)
        set_icon(self)
        self.geometry("500x380")
        self.minsize(460, 360)
        self.q: queue.Queue = queue.Queue()
        self.info: Info | None = None
        self.job: Job | None = None
        self.path: str | None = None
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="we", padx=16, pady=(14, 4))
        ctk.CTkLabel(head, text="Crusher", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.kind_lbl = ctk.CTkLabel(head, text="", text_color="gray")
        self.kind_lbl.pack(side="left", padx=10, pady=(6, 0))
        ctk.CTkButton(head, text="⚙", width=34, command=self.open_settings).pack(side="right")

        box = ctk.CTkFrame(self)
        box.grid(row=1, column=0, sticky="we", padx=16, pady=6)
        box.grid_columnconfigure(0, weight=1)
        self.file_lbl = ctk.CTkLabel(box, text="No file selected", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.file_lbl.grid(row=0, column=0, sticky="we", padx=10, pady=(8, 0))
        self.meta_lbl = ctk.CTkLabel(box, text="Video, audio, GIF, image, PDF, Office – or anything (zip)",
                                     anchor="w", text_color="gray")
        self.meta_lbl.grid(row=1, column=0, sticky="we", padx=10, pady=(0, 8))
        self.browse_btn = ctk.CTkButton(box, text="Browse…", width=90, command=self.browse)
        self.browse_btn.grid(row=0, column=1, rowspan=2, padx=10)

        tbox = ctk.CTkFrame(self, fg_color="transparent")
        tbox.grid(row=2, column=0, sticky="we", padx=16, pady=(8, 0))
        tbox.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tbox, text="Target").grid(row=0, column=0, padx=(0, 10))
        self.slider = ctk.CTkSlider(tbox, from_=1, to=100, number_of_steps=99, command=self.on_slider)
        self.slider.grid(row=0, column=1, sticky="we")
        self.entry = ctk.CTkEntry(tbox, width=60, justify="right")
        self.entry.grid(row=0, column=2, padx=(10, 4))
        ctk.CTkLabel(tbox, text="MB").grid(row=0, column=3)
        self.entry.bind("<Return>", self.on_entry)
        self.entry.bind("<FocusOut>", self.on_entry)

        self.plan_lbl = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color="gray",
                                     wraplength=460)
        self.plan_lbl.grid(row=3, column=0, sticky="we", padx=18, pady=(2, 6))
        self.bar = ctk.CTkProgressBar(self)
        self.bar.set(0)
        self.bar.grid(row=4, column=0, sticky="we", padx=16, pady=(6, 2))
        self.status = ctk.CTkLabel(self, text="", anchor="w")
        self.status.grid(row=5, column=0, sticky="we", padx=18)
        self.go_btn = ctk.CTkButton(self, text="Crush", height=38, font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self.toggle)
        self.go_btn.grid(row=6, column=0, sticky="we", padx=16, pady=(8, 16))
        self.grid_rowconfigure(6, weight=1)

        self.set_target(target_override or cfg["targets"]["video"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll)
        if initial:
            self.load(initial, auto)
        self.after(50, self.bring_front)

    # ---------------------------------------------------------------- helpers
    def bring_front(self):
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def set_status(self, text, error=False):
        self.status.configure(text=text, text_color=RED if error else ("gray10", "gray90"))

    def target_mb(self) -> float:
        try:
            return max(0.01, float(self.entry.get().replace(",", ".")))
        except ValueError:
            return 8.0

    def set_target(self, mb: float):
        self.slider.set(min(100, max(1, mb)))
        self.entry.delete(0, "end")
        self.entry.insert(0, f"{mb:g}")
        self.update_plan()

    def on_slider(self, v):
        self.entry.delete(0, "end")
        self.entry.insert(0, f"{round(v):g}")
        self.update_plan()

    def on_entry(self, _=None):
        self.set_target(self.target_mb())

    def update_plan(self):
        if not self.info:
            self.plan_lbl.configure(text="")
            return
        tb = int(self.target_mb() * MB)
        if self.info.size <= tb:
            self.plan_lbl.configure(text="✔ Already under target – nothing to do", text_color=GREEN)
            return
        try:
            self.plan_lbl.configure(text=engines.preview(self.info, tb, self.cfg), text_color="gray")
        except Exception as e:  # noqa: BLE001
            self.plan_lbl.configure(text=str(e).replace("\n", " "), text_color=RED)

    # ---------------------------------------------------------------- loading
    def browse(self):
        pats = " ".join("*" + e for e in engines.all_exts())
        f = filedialog.askopenfilename(parent=self, title="Choose a file",
                                       filetypes=[("Supported", pats), ("All files", "*.*")])
        if f:
            self.load(f)

    def load(self, path: str, auto: bool = False):
        path = os.path.abspath(path)
        self.path, self.info = path, None
        kind = engines.engine_for(path).KIND
        self.file_lbl.configure(text=Path(path).name)
        self.kind_lbl.configure(text=KIND_LABELS[kind])
        self.meta_lbl.configure(text="Reading…")
        self.plan_lbl.configure(text="")
        self.bar.set(0)
        self.set_status("")
        if self.target_override is None:
            self.set_target(self.cfg["targets"][kind])
        if kind in NEEDS_FFMPEG and not find_tool("ffprobe", self.cfg):
            self.meta_lbl.configure(text=fmt_size(os.path.getsize(path)))
            self.set_status("FFmpeg not found – see ⚙ Settings", error=True)
            messagebox.showerror(APP_NAME, MISSING_FFMPEG_MSG, parent=self)
            return

        def work():
            try:
                self.q.put(("info", path, engines.analyze(path, self.cfg), auto))
            except Exception as e:  # noqa: BLE001
                self.q.put(("probe_err", path, str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- crushing
    def toggle(self):
        if self.job:
            self.job.cancel()
            self.set_status("Cancelling…")
        else:
            self.start()

    def start(self):
        if not self.path or not self.info:
            self.browse()
            return
        target = self.target_mb()
        if self.info.size <= target * MB:
            messagebox.showinfo(APP_NAME, f"This file is already {fmt_size(self.info.size)}, under "
                                          f"{target:g} MB. Nothing to do.", parent=self)
            return
        job = Job(self.path, target, dict(self.cfg), lambda f, t: self.q.put(("progress", f, t)))
        self.job, info = job, self.info
        self.go_btn.configure(text="Cancel", fg_color=("#c0392b", "#a93226"), hover_color=("#a93226", "#922b21"))
        for w in (self.browse_btn, self.slider, self.entry):
            w.configure(state="disabled")

        def work():
            try:
                self.q.put(("done", engines.crush(job, info), target))
            except Cancelled:
                self.q.put(("cancelled",))
            except Exception as e:  # noqa: BLE001
                self.q.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def finish(self):
        self.job = None
        theme = ctk.ThemeManager.theme["CTkButton"]
        self.go_btn.configure(text="Crush", fg_color=theme["fg_color"], hover_color=theme["hover_color"])
        for w in (self.browse_btn, self.slider, self.entry):
            w.configure(state="normal")

    def poll(self):
        try:
            while True:
                self.handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def handle(self, msg):
        kind = msg[0]
        if kind == "info":
            _, path, info, auto = msg
            if path != self.path:
                return
            self.info = info
            self.meta_lbl.configure(text=info.summary)
            self.update_plan()
            if auto:
                self.start()
        elif kind == "probe_err":
            if msg[1] == self.path:
                self.meta_lbl.configure(text="Can't read this file")
                messagebox.showerror(APP_NAME, msg[2], parent=self)
        elif kind == "progress":
            _, f, text = msg
            self.bar.set(f)
            self.set_status(f"{text}  ·  {f * 100:.0f}%")
        elif kind == "done":
            _, r, target = msg
            self.finish()
            self.bar.set(1)
            if r.skipped:
                self.set_status("Already under target – nothing to do")
                return
            self.set_status(f"Saved {fmt_size(r.out_size)} → {Path(r.out).name}", error=r.missed)
            self.bell()
            DoneDialog(self, r, target)
        elif kind == "cancelled":
            self.finish()
            self.bar.set(0)
            self.set_status("Cancelled")
        elif kind == "error":
            self.finish()
            self.bar.set(0)
            self.set_status("Failed", error=True)
            messagebox.showerror(APP_NAME, msg[1], parent=self)

    def open_settings(self):
        SettingsWindow(self, self.cfg, on_save=self.on_settings_saved)

    def on_settings_saved(self):
        if not self.job and self.target_override is None:
            kind = self.info.kind if self.info else "video"
            self.set_target(self.cfg["targets"][kind])
        self.update_plan()

    def on_close(self):
        if self.job:
            if not messagebox.askyesno(APP_NAME, "Still crushing. Cancel it and quit?", parent=self):
                return
            self.job.cancel()
        self.destroy()


def run_gui(cfg: dict, initial: str | None, auto: bool, target: float | None = None) -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    if IS_WIN:  # own taskbar identity so Windows shows Crusher's icon
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Crusher.App")
        except (AttributeError, OSError):
            pass
    App(cfg, initial, auto, target).mainloop()
