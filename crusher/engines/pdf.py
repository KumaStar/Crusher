"""PDF: lossless stream cleanup first, then recompress embedded images at stepped quality levels.
Text and vector graphics are never touched, so they stay sharp."""
from __future__ import annotations

import io
import os
import shutil

from ..core import MB, CrushError, Info, Job, Result, fmt_size, safe_remove

KIND = "pdf"
EXTS = (".pdf",)
# (max image side in px, JPEG quality). First level = lossless only.
LEVELS = [(None, None), (2400, 85), (1800, 75), (1400, 65), (1100, 55), (850, 45), (650, 35), (500, 30)]
MIN_IMAGE_BYTES = 20_000


def _pikepdf():
    try:
        import pikepdf
        return pikepdf
    except ImportError:
        raise CrushError("PDF support needs pikepdf:  pip install pikepdf")


def analyze(path: str, cfg: dict) -> Info:
    pikepdf = _pikepdf()
    try:
        with pikepdf.open(path) as pdf:
            pages = len(pdf.pages)
            images = sum(1 for o in pdf.objects if isinstance(o, pikepdf.Stream)
                         and o.get("/Subtype") == pikepdf.Name.Image)
    except pikepdf.PasswordError:
        raise CrushError("This PDF is password-protected.")
    except Exception as e:  # noqa: BLE001
        raise CrushError(f"Can't read this PDF: {e}")
    size = os.path.getsize(path)
    return Info(path, size, KIND, f"{fmt_size(size)} · {pages} page{'s' * (pages != 1)} · {images} images",
                dict(pages=pages, images=images))


def preview(info: Info, target: int, cfg: dict) -> str:
    if not info.data["images"]:
        return "→ lossless cleanup only (no images to shrink)"
    return "→ recompresses images step by step · text stays sharp"


def _shrink_image(pikepdf, obj, max_side: int, q: int) -> None:
    from PIL import Image
    from pikepdf import Name, PdfImage
    if obj.get("/ImageMask") or int(obj.get("/BitsPerComponent", 8)) == 1:
        return
    raw_len = len(obj.read_raw_bytes())
    if raw_len < MIN_IMAGE_BYTES:
        return
    try:
        pil = PdfImage(obj).as_pil_image()
    except Exception:  # noqa: BLE001  (JBIG2, JPX, exotic colour spaces...)
        return
    if pil.mode == "1":
        return
    if pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")
    if max(pil.size) > max_side:
        pil.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=q, optimize=True)
    if buf.tell() >= raw_len:
        return
    obj.write(buf.getvalue(), filter=Name.DCTDecode)
    obj.Width, obj.Height = pil.width, pil.height
    obj.ColorSpace = Name.DeviceGray if pil.mode == "L" else Name.DeviceRGB
    obj.BitsPerComponent = 8
    for k in ("/DecodeParms", "/Decode"):
        if k in obj:
            del obj[k]


def _build(job: Job, out: str, level, lo: float, hi: float) -> None:
    pikepdf = _pikepdf()
    max_side, q = level
    with pikepdf.open(job.src) as pdf:
        if max_side:
            smasks = {o.SMask.objgen for o in pdf.objects
                      if isinstance(o, pikepdf.Stream) and "/SMask" in o}
            imgs = [o for o in pdf.objects if isinstance(o, pikepdf.Stream)
                    and o.get("/Subtype") == pikepdf.Name.Image and o.objgen not in smasks]
            for i, o in enumerate(imgs):
                job.check()
                job.progress(lo + (hi - lo) * i / max(1, len(imgs)),
                             f"Images ≤{max_side}px, quality {q}")
                _shrink_image(pikepdf, o, max_side, q)
        else:
            job.progress(lo, "Lossless cleanup")
        try:
            pdf.remove_unreferenced_resources()
        except Exception:  # noqa: BLE001
            pass
        pdf.save(out, compress_streams=True, recompress_flate=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)


def crush(job: Job, info: Info) -> Result:
    out = job.out_path(".pdf")
    tmp = job.tempdir()
    best, best_size, best_level = None, info.size, None
    levels = LEVELS if info.data["images"] else LEVELS[:1]
    try:
        for i, level in enumerate(levels):
            cand = os.path.join(tmp, f"l{i}.pdf")
            _build(job, cand, level, i / len(levels), (i + 1) / len(levels))
            size = os.path.getsize(cand)
            if size < best_size:
                best, best_size, best_level = cand, size, level
            if size <= job.target:
                break
        if not best:
            raise CrushError("This PDF is already as small as Crusher can make it.")
        shutil.move(best, out)
    except BaseException:
        safe_remove(out)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    detail = ("lossless" if not best_level[0] else f"images ≤{best_level[0]}px · q{best_level[1]}")
    return job.result(out, detail, missed=best_size > job.target)
