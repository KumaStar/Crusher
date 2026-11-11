"""Audio: re-encode to MP3 at the bitrate that fits the target (verify & retry)."""
from __future__ import annotations

import math
import os

from ..core import MB, CrushError, Info, Job, Result, ffprobe_json, fmt_size, fmt_time, safe_remove

KIND = "audio"
EXTS = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma", ".aif",
        ".aiff", ".alac", ".amr", ".ape", ".wv")
OVERHEAD = 0.98
MIN_KBPS = 16


def analyze(path: str, cfg: dict) -> Info:
    data = ffprobe_json(path, cfg)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not a:
        raise CrushError("No audio stream found in this file.")
    dur = float(data.get("format", {}).get("duration") or a.get("duration") or 0)
    if dur <= 0:
        raise CrushError("Could not determine the audio duration.")
    ch = int(a.get("channels") or 2)
    size = os.path.getsize(path)
    return Info(path, size, KIND,
                f"{fmt_size(size)} · {fmt_time(dur)} · {a.get('codec_name', '?')} · "
                f"{int(a.get('sample_rate') or 0) // 1000} kHz · {ch} ch",
                dict(duration=dur, channels=ch))


def _kbps(info: Info, target: int) -> int:
    k = int(target * 8 * OVERHEAD / info.data["duration"] / 1000)
    if k < MIN_KBPS:
        need = MIN_KBPS * 1000 * info.data["duration"] / 8 / OVERHEAD / MB
        raise CrushError(f"Too long to fit in {target / MB:g} MB – needs at least ~{math.ceil(need)} MB.")
    return _snap(min(k, 320))


MP3_RATES = (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)


def _snap(k: int) -> int:
    """MP3 only supports fixed bitrates: take the largest one that fits."""
    return max([r for r in MP3_RATES if r <= k] or [8])


def _settings(kbps: int, channels: int) -> list[str]:
    ch = 1 if kbps < 48 or channels == 1 else 2
    rate = "22050" if kbps < 40 else "32000" if kbps < 64 else "44100"
    return ["-c:a", "libmp3lame", "-b:a", f"{kbps}k", "-ac", str(ch), "-ar", rate]


def preview(info: Info, target: int, cfg: dict) -> str:
    k = _kbps(info, target)
    ch = "mono" if k < 48 or info.data["channels"] == 1 else "stereo"
    return f"→ MP3 {k} kbps {ch}"


def crush(job: Job, info: Info) -> Result:
    kbps = _kbps(info, job.target)
    out = job.out_path(".mp3")
    try:
        for attempt in range(3):
            job.run_ffmpeg(["-i", job.src, "-map", "0:a:0", "-vn", "-map_metadata", "-1"]
                           + _settings(kbps, info.data["channels"]) + [out],
                           info.data["duration"], 0, 1,
                           "Encoding" if attempt == 0 else f"Over target – retry {attempt}")
            size = os.path.getsize(out)
            if size <= job.target:
                return job.result(out, f"MP3 {kbps} kbps")
            kbps = _snap(min(kbps - 1, int(kbps * job.target / size * 0.95)))
            if kbps < 8:
                break
        raise CrushError(f"Couldn't get under {job.target / MB:g} MB (best {fmt_size(size)}).")
    except BaseException:
        safe_remove(out)
        raise
