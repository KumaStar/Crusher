"""Anything else: pack into a max-compression ZIP (opens natively on Windows, macOS, Android)."""
from __future__ import annotations

import os
import zipfile

from ..core import Info, Job, Result, fmt_size, safe_remove

KIND = "other"
EXTS: tuple = ()          # fallback for every other extension
ALREADY_COMPRESSED = (".zip", ".7z", ".rar", ".gz", ".bz2", ".xz", ".zst", ".jar", ".apk",
                      ".msi", ".cab", ".dmg", ".iso")
CHUNK = 1 << 20


def analyze(path: str, cfg: dict) -> Info:
    size = os.path.getsize(path)
    ext = os.path.splitext(path)[1].lower() or "file"
    return Info(path, size, KIND, f"{fmt_size(size)} · {ext} file", dict(ext=ext))


def preview(info: Info, target: int, cfg: dict) -> str:
    if info.data["ext"] in ALREADY_COMPRESSED:
        return "→ ZIP · already compressed, will barely shrink"
    return "→ ZIP (max compression) · results depend on the file"


def crush(job: Job, info: Info) -> Result:
    out = job.out_path(os.path.splitext(job.src)[1] + ".zip")
    try:
        done = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z, \
                open(job.src, "rb") as src, \
                z.open(os.path.basename(job.src), "w", force_zip64=info.size > 2**31) as dst:
            while chunk := src.read(CHUNK):
                job.check()
                dst.write(chunk)
                done += len(chunk)
                job.progress(done / max(1, info.size), "Zipping")
    except BaseException:
        safe_remove(out)
        raise
    return job.result(out, "ZIP · deflate level 9", missed=os.path.getsize(out) > job.target)
