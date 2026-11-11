"""Engine registry. Each engine module exposes KIND, EXTS, analyze(), preview(), crush()."""
from __future__ import annotations

import os

from ..core import Info, Job, Result
from . import archive, audio, gif, image, office, pdf, video

ENGINES = [video, audio, gif, image, pdf, office]
FALLBACK = archive


def engine_for(path: str):
    ext = os.path.splitext(path)[1].lower()
    for e in ENGINES:
        if ext in e.EXTS:
            return e
    return FALLBACK


def engine_by_kind(kind: str):
    return next((e for e in ENGINES + [FALLBACK] if e.KIND == kind), FALLBACK)


def analyze(path: str, cfg: dict) -> Info:
    return engine_for(path).analyze(path, cfg)


def preview(info: Info, target: int, cfg: dict) -> str:
    return engine_by_kind(info.kind).preview(info, target, cfg)


def crush(job: Job, info: Info) -> Result:
    if info.size <= job.target:
        return Result(job.src, job.src, info.size, info.size, skipped=True)
    return engine_by_kind(info.kind).crush(job, info)


def all_exts() -> list[str]:
    return sorted({x for e in ENGINES for x in e.EXTS})
