"""GIF: re-encode with an optimised palette, stepping down fps -> colours -> size until it fits."""
from __future__ import annotations

import math
import os

from ..core import MB, CrushError, Info, Job, Result, ffprobe_json, fmt_size, fmt_time, safe_remove

KIND = "gif"
EXTS = (".gif",)
MAX_ATTEMPTS = 7


def _rate(s):
    try:
        n, _, d = (s or "0/1").partition("/")
        return float(n) / float(d or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def analyze(path: str, cfg: dict) -> Info:
    data = ffprobe_json(path, cfg)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise CrushError("Not a readable GIF.")
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    fps = _rate(v.get("avg_frame_rate")) or _rate(v.get("r_frame_rate")) or 10.0
    fps = min(fps, 50.0)
    size = os.path.getsize(path)
    return Info(path, size, KIND, f"{fmt_size(size)} · {fmt_time(dur)} · {w}×{h} @ {fps:.3g} fps",
                dict(width=w, height=h, fps=fps, duration=dur))


def preview(info: Info, target: int, cfg: dict) -> str:
    return "→ GIF · lowers frame rate, colours, then size until it fits"


def crush(job: Job, info: Info) -> Result:
    d = info.data
    w, fps, colors = d["width"], min(d["fps"], 20.0), 256
    out = job.out_path(".gif")
    size = 0
    try:
        for attempt in range(MAX_ATTEMPTS):
            vf = (f"fps={fps:.3g},scale={w}:-1:flags=lanczos,split[a][b];"
                  f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
                  f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
            job.run_ffmpeg(["-i", job.src, "-vf", vf, "-loop", "0", out], d["duration"],
                           attempt / MAX_ATTEMPTS, (attempt + 1) / MAX_ATTEMPTS,
                           f"Attempt {attempt + 1}: {w}px · {fps:.3g} fps · {colors} colours")
            size = os.path.getsize(out)
            if size <= job.target:
                return job.result(out, f"{w}px wide · {fps:.3g} fps · {colors} colours")
            r = job.target / size * 0.9
            if fps > 12 and r > 0.5:
                fps = max(10.0, fps * r)
            elif colors > 64 and r > 0.7:
                colors //= 2
            else:
                w = max(64, int(w * math.sqrt(r)) // 2 * 2)
                if w == 64 and attempt > 3:
                    break
        raise CrushError(f"Couldn't get this GIF under {job.target / MB:g} MB "
                         f"(best {fmt_size(size)}). Try converting it to video instead.")
    except BaseException:
        safe_remove(out)
        raise
