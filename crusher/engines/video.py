"""Video: 2-pass libx264 + AAC with bitrates calculated from the target, auto downscale, verify & retry."""
from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass

from ..core import MB, CrushError, Info, Job, Result, ffprobe_json, fmt_size, fmt_time, safe_remove

KIND = "video"
EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".ts", ".mts",
        ".m2ts", ".3gp", ".mpg", ".mpeg", ".vob", ".ogv")

OVERHEAD = 0.97          # container headroom
MIN_VIDEO_KBPS = 40
BPP_MIN = 0.06           # bits per pixel per frame considered "good enough"
LADDER = [1080, 720, 540, 480, 360, 240]
MAX_RETRIES = 2
PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower"]


@dataclass
class Plan:
    video_kbps: int
    audio_kbps: int
    audio_ch: int
    out_w: int
    out_h: int
    fps: float
    scale: bool
    fps_change: bool
    portrait: bool

    def describe(self) -> str:
        audio = f"audio {self.audio_kbps} kbps" if self.audio_kbps else "no audio"
        return (f"→ {self.out_w}×{self.out_h} @ {self.fps:g} fps · "
                f"video {self.video_kbps:,} kbps · {audio}")


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _rate(s: str | None) -> float:
    try:
        n, _, d = (s or "0/1").partition("/")
        return float(n) / float(d or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def analyze(path: str, cfg: dict) -> Info:
    data = ffprobe_json(path, cfg)
    streams = data.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"
               and not s.get("disposition", {}).get("attached_pic")), None)
    if not vs:
        raise CrushError("No video stream found in this file.")
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or vs.get("duration") or 0)
    if duration <= 0:
        raise CrushError("Could not determine the video's duration.")
    w, h = int(vs.get("width") or 0), int(vs.get("height") or 0)
    rot = 0
    for sd in vs.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = rot or int(float(vs.get("tags", {}).get("rotate", 0) or 0))
    if abs(rot) % 180 == 90:          # ffmpeg auto-rotates -> use displayed dims
        w, h = h, w
    fps = _rate(vs.get("avg_frame_rate")) or _rate(vs.get("r_frame_rate")) or 30.0
    if fps > 240:
        fps = 30.0
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    size = os.path.getsize(path)
    return Info(path, size, KIND,
                f"{fmt_size(size)} · {fmt_time(duration)} · {w}×{h} @ {fps:.3g} fps"
                + ("" if has_audio else " · no audio"),
                dict(duration=duration, width=w, height=h, fps=fps, has_audio=has_audio))


def plan(info: Info, target: int, max_short="auto") -> Plan:
    d = info.data
    total_kbps = target * 8 * OVERHEAD / d["duration"] / 1000
    if d["has_audio"]:
        a, ch = ((128, 2) if total_kbps >= 1500 else (96, 2) if total_kbps >= 600
                 else (64, 2) if total_kbps >= 250 else (32, 1))
    else:
        a, ch = 0, 0
    v = total_kbps - a
    if v < MIN_VIDEO_KBPS:
        need = (MIN_VIDEO_KBPS + (32 if d["has_audio"] else 0)) * 1000 * d["duration"] / 8 / OVERHEAD / MB
        raise CrushError(f"Too long to fit in {target / MB:g} MB at watchable quality – "
                         f"needs at least ~{math.ceil(need)} MB.")
    w, h = d["width"], d["height"]
    portrait = h > w
    src_short, src_long = min(w, h), max(w, h)
    cap = src_short if str(max_short) == "auto" else min(src_short, int(max_short))
    cap = _even(cap)
    sizes = [cap] + [s for s in LADDER if s < cap]
    fps_opts = [min(d["fps"], 60.0)] + ([30.0] if d["fps"] > 31 else [])
    chosen = None
    for s in sizes:
        long_side = _even(src_long * s / src_short)
        for f in fps_opts:
            if v * 1000 / (s * long_side * f) >= BPP_MIN:
                chosen = (s, long_side, f)
                break
        if chosen:
            break
    if not chosen:
        s = sizes[-1]
        chosen = (s, _even(src_long * s / src_short), fps_opts[-1])
    s, long_side, f = chosen
    out_w, out_h = (s, long_side) if portrait else (long_side, s)
    return Plan(int(v), a, ch, out_w, out_h, round(f, 3), s < src_short, f < d["fps"] - 0.5, portrait)


def preview(info: Info, target: int, cfg: dict) -> str:
    return plan(info, target, cfg.get("max_height", "auto")).describe()


def crush(job: Job, info: Info) -> Result:
    p = plan(info, job.target, job.cfg.get("max_height", "auto"))
    duration = info.data["duration"]
    out = job.out_path(".mp4")
    tmp = job.tempdir()
    passlog = os.path.join(tmp, "pass")
    vf = []
    if p.scale:
        vf.append(f"scale={p.out_w}:-2:flags=lanczos" if p.portrait else f"scale=-2:{p.out_h}:flags=lanczos")
    if p.fps_change:
        vf.append(f"fps={p.fps:g}")
    vf.append("format=yuv420p")
    preset = job.cfg.get("x264_preset", "medium")
    preset = preset if preset in PRESETS else "medium"
    head = ["-i", job.src, "-map", "0:v:0"]

    def vargs(kbps: int, n: int) -> list[str]:
        return ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", preset,
                "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k",
                "-pass", str(n), "-passlogfile", passlog]

    audio = (["-map", "0:a:0", "-c:a", "aac", "-b:a", f"{p.audio_kbps}k", "-ac", str(p.audio_ch)]
             if p.audio_kbps else ["-an"])
    tail = ["-movflags", "+faststart", "-map_metadata", "-1", out]
    kbps = p.video_kbps
    try:
        job.run_ffmpeg(head + vargs(kbps, 1) + ["-an", "-f", "null", "-"], duration, 0, 0.5,
                       "Pass 1 of 2 – analysing")
        attempt = 0
        while True:
            attempt += 1
            label = "Pass 2 of 2 – encoding" if attempt == 1 else f"Over target – retry {attempt - 1}"
            job.run_ffmpeg(head + vargs(kbps, 2) + audio + tail, duration, 0.5, 1.0, label)
            size = os.path.getsize(out)
            if size <= job.target:
                break
            if attempt > MAX_RETRIES:
                raise CrushError(f"Couldn't get under {job.target / MB:g} MB (best {fmt_size(size)}). "
                                 "Try a bigger target or a lower max resolution.")
            kbps = int(kbps * job.target / size * 0.95)
            if kbps < MIN_VIDEO_KBPS:
                raise CrushError("Target is too small for this video.")
    except BaseException:
        safe_remove(out)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    p.video_kbps = kbps
    return job.result(out, f"{p.out_w}×{p.out_h} @ {p.fps:g} fps")
