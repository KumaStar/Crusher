"""Images: binary-search JPEG/WebP quality, then downscale, until it fits. Pure Pillow."""
from __future__ import annotations

import io
import os

from ..core import MB, CrushError, Info, Job, Result, fmt_size

KIND = "image"
EXTS = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".tif", ".tiff", ".tga", ".ico")
SCALES = [1.0, 0.85, 0.7, 0.55, 0.42, 0.32, 0.24, 0.18, 0.12, 0.08]
Q_MIN, Q_MAX = 40, 92

try:  # optional HEIC/AVIF support (pip install pillow-heif)
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
    EXTS += (".heic", ".heif", ".avif")
except Exception:  # noqa: BLE001
    pass


def _open(path):
    from PIL import Image, ImageOps
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im


def _has_alpha(im) -> bool:
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        alpha = im.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255
    return False


def _out_format(path: str, alpha: bool) -> tuple[str, str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".webp" or alpha:
        return "WEBP", ".webp"
    return "JPEG", ".jpg"


def analyze(path: str, cfg: dict) -> Info:
    try:
        im = _open(path)
    except Exception as e:  # noqa: BLE001
        raise CrushError(f"Can't open this image: {e}")
    alpha = _has_alpha(im)
    size = os.path.getsize(path)
    return Info(path, size, KIND, f"{fmt_size(size)} · {im.width}×{im.height} · {im.format or im.mode}"
                + (" · transparent" if alpha else ""),
                dict(width=im.width, height=im.height, alpha=alpha))


def preview(info: Info, target: int, cfg: dict) -> str:
    fmt, _ = _out_format(info.path, info.data["alpha"])
    if info.path.lower().endswith(".png") and info.data["alpha"]:
        return "→ optimised PNG, or WebP (keeps transparency) if needed"
    return f"→ {fmt} · best quality that fits, downscaled only if needed"


def _encode(im, fmt: str, q: int) -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True,
                icc_profile=im.info.get("icc_profile"))
    else:
        im.save(buf, "WEBP", quality=q, method=6)
    return buf.getvalue()


def _fit(im, fmt: str, target: int, job: Job | None, lo: float, hi: float) -> bytes | None:
    """Largest quality in [Q_MIN, Q_MAX] that fits, or None."""
    best, a, b, steps = None, Q_MIN, Q_MAX, 0
    while a <= b:
        if job:
            job.check()
        q = (a + b) // 2
        data = _encode(im, fmt, q)
        steps += 1
        if len(data) <= target:
            best, a = data, q + 1
        else:
            b = q - 1
    return best


def crush(job: Job, info: Info) -> Result:
    from PIL import Image
    im = _open(job.src)
    alpha = info.data["alpha"]
    fmt, ext = _out_format(job.src, alpha)

    # transparent PNG: try a lossless-ish palette PNG first (keeps the format)
    if alpha and job.src.lower().endswith(".png"):
        job.progress(0.05, "Trying optimised PNG")
        buf = io.BytesIO()
        im.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", optimize=True)
        if buf.tell() <= job.target:
            return _write(job, buf.getvalue(), ".png", "palette PNG")

    im = im.convert("RGBA" if alpha and fmt == "WEBP" else "RGB")
    for i, s in enumerate(SCALES):
        job.progress(i / len(SCALES), f"Trying {int(s * 100)}% size")
        frame = im if s == 1.0 else im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                                              Image.LANCZOS)
        data = _fit(frame, fmt, job.target, job, 0, 1)
        if data:
            return _write(job, data, ext, f"{fmt} · {frame.width}×{frame.height}")
    raise CrushError(f"Couldn't get this image under {job.target / MB:g} MB.")


def _write(job: Job, data: bytes, ext: str, detail: str) -> Result:
    out = job.out_path(ext)
    with open(out, "wb") as f:
        f.write(data)
    job.progress(1, "Done")
    return job.result(out, detail)
