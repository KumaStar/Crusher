"""Portable core: config, tool discovery, job runner, helpers. No UI, no OS-specific UI code."""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "Crusher"
MB = 1_000_000                      # decimal MB: stricter than MiB, so always safe
IS_WIN = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0

KINDS = ["video", "audio", "gif", "image", "pdf", "office", "other"]
KIND_LABELS = {"video": "Video", "audio": "Audio", "gif": "GIF", "image": "Image",
               "pdf": "PDF", "office": "Office / eBook", "other": "Other (zip)"}


# --------------------------------------------------------------------------- config
def config_dir() -> Path:
    if IS_WIN:
        return Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "crusher"


CONFIG_FILE = config_dir() / "config.json"
DEFAULTS = {
    "targets": {k: 8.0 for k in KINDS},  # MB per file kind
    "max_height": "auto",                # video: cap on the short side
    "output_dir": "",                    # "" = next to the source
    "suffix": "_crushed",
    "x264_preset": "medium",
    "ffmpeg_path": "",                   # folder with ffmpeg/ffprobe (optional)
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "target_mb" in data and "targets" not in data:   # v1 config migration
            data["targets"] = {"video": data["target_mb"]}
        for k, v in data.items():
            if k == "targets" and isinstance(v, dict):
                cfg["targets"].update({kk: float(vv) for kk, vv in v.items() if kk in KINDS})
            elif k in DEFAULTS:
                cfg[k] = v
    except FileNotFoundError:
        save_config(cfg)
    except (OSError, ValueError, TypeError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({k: cfg[k] for k in DEFAULTS}, f, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------- tools
def find_tool(name: str, cfg: dict) -> str | None:
    """Locate ffmpeg/ffprobe: settings override, PATH, then common install dirs."""
    exe = name + (".exe" if IS_WIN else "")
    override = (cfg.get("ffmpeg_path") or "").strip().strip('"')
    if override:
        p = Path(override)
        if p.is_file():
            p = p.parent
        for c in (p / exe, p / "bin" / exe):
            if c.is_file():
                return str(c)
    found = shutil.which(name)
    if found:
        return found
    here = Path(__file__).resolve().parent.parent
    cands = [here / exe, here / "ffmpeg" / exe, here / "ffmpeg" / "bin" / exe]
    if getattr(sys, "frozen", False):  # bundled build: ffmpeg sits next to Crusher.exe
        exe_dir = Path(sys.executable).resolve().parent
        cands = [exe_dir / exe, exe_dir / "ffmpeg" / exe] + cands
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA", "")
        cands += [Path(local) / APP_NAME / "ffmpeg" / exe,
                  Path(local) / "Microsoft" / "WinGet" / "Links" / exe,
                  Path(r"C:\ProgramData\chocolatey\bin") / exe,
                  Path(r"C:\ffmpeg\bin") / exe,
                  Path.home() / "scoop" / "shims" / exe]
        cands += [Path(p) for p in glob.glob(os.path.join(
            local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "*", "bin", exe))]
    else:
        cands += [Path("/opt/homebrew/bin") / exe, Path("/usr/local/bin") / exe,
                  Path("/usr/bin") / exe, config_dir() / "ffmpeg" / exe]
    for c in cands:
        if c.is_file():
            return str(c)
    return None


MISSING_FFMPEG_MSG = (
    "FFmpeg was not found (needed for video, audio and GIF).\n\n"
    "Windows: winget install Gyan.FFmpeg  /  choco install ffmpeg\n"
    "macOS:   brew install ffmpeg\n"
    "Linux:   sudo apt install ffmpeg\n\n"
    "Or download a build and set its folder in ⚙ Settings.")


# --------------------------------------------------------------------------- results / errors
class CrushError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Info:
    """What analyze() found out about a file."""
    path: str
    size: int
    kind: str
    summary: str                     # one line for the UI
    data: dict = field(default_factory=dict)


@dataclass
class Result:
    src: str
    out: str
    src_size: int
    out_size: int
    detail: str = ""
    elapsed: float = 0.0
    skipped: bool = False            # already under target
    missed: bool = False             # best effort, still over target


# --------------------------------------------------------------------------- job
class Job:
    """One crush operation. Engines call progress()/check()/run_ffmpeg()."""

    def __init__(self, src: str, target_mb: float, cfg: dict, on_progress=None):
        self.src = src
        self.target = int(target_mb * MB)
        self.cfg = cfg
        self.on_progress = on_progress or (lambda f, t: None)
        self._cancel = threading.Event()
        self._proc: subprocess.Popen | None = None
        self.t0 = time.time()

    # -- control
    def cancel(self) -> None:
        self._cancel.set()
        p = self._proc
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    def progress(self, frac: float, text: str) -> None:
        self.on_progress(max(0.0, min(1.0, frac)), text)

    # -- helpers
    def tool(self, name: str) -> str:
        t = find_tool(name, self.cfg)
        if not t:
            raise CrushError(MISSING_FFMPEG_MSG)
        return t

    def out_path(self, ext: str) -> str:
        p = Path(self.src)
        out_dir = Path(self.cfg.get("output_dir") or p.parent)
        out_dir.mkdir(parents=True, exist_ok=True)
        base = p.stem + (self.cfg.get("suffix") or "_crushed")
        out = out_dir / f"{base}{ext}"
        n = 2
        while out.exists() or out.resolve() == p.resolve():
            out = out_dir / f"{base} ({n}){ext}"
            n += 1
        return str(out)

    def tempdir(self) -> str:
        return tempfile.mkdtemp(prefix="crusher_")

    def run_ffmpeg(self, args: list[str], duration: float = 0, lo: float = 0, hi: float = 1,
                   label: str = "") -> None:
        """Run ffmpeg (args without the binary), mapping its progress into [lo, hi]."""
        self.check()
        self.progress(lo, label)
        cmd = [self.tool("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
               "-progress", "pipe:1", "-nostats"] + args
        tail: deque[str] = deque(maxlen=40)
        self._proc = proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
        if self._cancel.is_set():
            proc.kill()
        reader = threading.Thread(target=lambda: tail.extend(l.rstrip() for l in proc.stderr),
                                  daemon=True)
        reader.start()
        for line in proc.stdout:
            key, _, val = line.strip().partition("=")
            if duration and key in ("out_time_us", "out_time_ms") and val.isdigit():
                self.progress(lo + (hi - lo) * min(1.0, int(val) / 1e6 / duration), label)
        proc.wait()
        reader.join(timeout=2)
        self._proc = None
        self.check()
        if proc.returncode != 0:
            msg = "\n".join(l for l in list(tail)[-8:] if l)
            raise CrushError(f"FFmpeg failed (exit {proc.returncode}):\n{msg}")

    def result(self, out: str, detail: str = "", missed: bool = False) -> Result:
        return Result(self.src, out, os.path.getsize(self.src), os.path.getsize(out),
                      detail, time.time() - self.t0, missed=missed)


def ffprobe_json(path: str, cfg: dict) -> dict:
    probe = find_tool("ffprobe", cfg)
    if not probe:
        raise CrushError(MISSING_FFMPEG_MSG)
    try:
        out = subprocess.run([probe, "-v", "error", "-print_format", "json",
                              "-show_format", "-show_streams", path],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL, timeout=60)
    except subprocess.TimeoutExpired:
        raise CrushError("ffprobe timed out reading the file.")
    if out.returncode != 0:
        raise CrushError("Can't read this file:\n" + out.stderr.strip()[-400:])
    return json.loads(out.stdout or "{}")


def safe_remove(path: str | None) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


# --------------------------------------------------------------------------- formatting
def fmt_size(n: int) -> str:
    if n >= 1000 * MB:
        return f"{n / (1000 * MB):.2f} GB"
    if n >= MB:
        return f"{n / MB:.2f} MB"
    return f"{n / 1000:.0f} KB"


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
