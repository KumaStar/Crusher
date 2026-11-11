"""Office & eBook files (docx/pptx/xlsx/odt/epub…) are zip containers: recompress the
pictures inside (same names and formats, so the document stays valid) and re-zip tighter."""
from __future__ import annotations

import io
import os
import shutil
import zipfile

from ..core import MB, CrushError, Info, Job, Result, fmt_size, safe_remove

KIND = "office"
EXTS = (".docx", ".docm", ".pptx", ".pptm", ".xlsx", ".xlsm", ".odt", ".odp", ".ods", ".odg", ".epub")
LEVELS = [(None, None), (2000, 85), (1600, 75), (1280, 65), (1024, 55), (800, 45), (640, 35)]
IMG_EXTS = (".jpg", ".jpeg", ".png")
MIN_IMAGE_BYTES = 30_000


def analyze(path: str, cfg: dict) -> Info:
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            img_bytes = sum(i.file_size for i in z.infolist() if i.filename.lower().endswith(IMG_EXTS))
    except zipfile.BadZipFile:
        raise CrushError("This file isn't a valid Office/eBook document (or it's encrypted).")
    size = os.path.getsize(path)
    n_img = sum(1 for n in names if n.lower().endswith(IMG_EXTS))
    return Info(path, size, KIND, f"{fmt_size(size)} · {n_img} pictures ({fmt_size(img_bytes)})",
                dict(images=n_img))


def preview(info: Info, target: int, cfg: dict) -> str:
    if not info.data["images"]:
        return "→ re-zip only (no pictures inside to shrink)"
    return "→ recompresses pictures inside · text and layout untouched"


def _shrink(data: bytes, ext: str, max_side: int, q: int) -> bytes:
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        return data
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    if ext in (".jpg", ".jpeg"):
        im.convert("L" if im.mode in ("L", "LA") else "RGB").save(buf, "JPEG", quality=q, optimize=True)
    else:  # keep PNG (content type must match); palette-quantise at lower levels
        if q <= 75:
            im = im.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE)
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue() if buf.tell() < len(data) else data


def _build(job: Job, out: str, level, lo: float, hi: float) -> None:
    max_side, q = level
    with zipfile.ZipFile(job.src) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        items = zin.infolist()
        for i, item in enumerate(items):
            job.check()
            if i % 5 == 0:
                job.progress(lo + (hi - lo) * i / len(items),
                             f"Pictures ≤{max_side}px, quality {q}" if max_side else "Re-zipping")
            data = zin.read(item)
            if item.filename == "mimetype":          # ODF/EPUB: must stay first & stored
                zout.writestr(item, data, compress_type=zipfile.ZIP_STORED)
                continue
            ext = os.path.splitext(item.filename)[1].lower()
            if max_side and ext in IMG_EXTS and len(data) > MIN_IMAGE_BYTES:
                data = _shrink(data, ext, max_side, q)
            zi = zipfile.ZipInfo(item.filename, item.date_time)
            zi.external_attr = item.external_attr
            zout.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def crush(job: Job, info: Info) -> Result:
    ext = os.path.splitext(job.src)[1].lower()
    out = job.out_path(ext)
    tmp = job.tempdir()
    best, best_size, best_level = None, info.size, None
    levels = LEVELS if info.data["images"] else LEVELS[:1]
    try:
        for i, level in enumerate(levels):
            cand = os.path.join(tmp, f"l{i}{ext}")
            _build(job, cand, level, i / len(levels), (i + 1) / len(levels))
            size = os.path.getsize(cand)
            if size < best_size:
                best, best_size, best_level = cand, size, level
            if size <= job.target:
                break
        if not best:
            raise CrushError("This document is already as small as Crusher can make it.")
        shutil.move(best, out)
    except BaseException:
        safe_remove(out)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    detail = "re-zipped" if not best_level[0] else f"pictures ≤{best_level[0]}px · q{best_level[1]}"
    return job.result(out, detail, missed=best_size > job.target)
