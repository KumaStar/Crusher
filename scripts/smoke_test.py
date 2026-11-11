"""Smoke test for a built Crusher binary (any OS).

    python scripts/smoke_test.py <path/to/Crusher binary> <path/to/ffmpeg>

Makes a test video, image, PDF and random file, crushes each with
`--crush FILE --nogui --target N` and checks the result exists and fits.
Exit code 0 = all passed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def make_files(d: Path, ffmpeg: str) -> list[tuple[Path, float]]:
    video = d / "video.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=8",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                    "-c:v", "libx264", "-b:v", "8M", "-c:a", "aac", "-shortest", str(video)], check=True)
    image = d / "image.png"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "mandelbrot=size=2400x1800", "-frames:v", "1", str(image)], check=True)
    pdf = d / "doc.pdf"
    Image.open(image).convert("RGB").save(pdf, quality=95)
    other = d / "data.txt"
    other.write_text("crusher smoke test line\n" * 200_000)
    return [(video, 2.0), (image, 0.5), (pdf, 0.3), (other, 1.0)]


def main() -> int:
    # absolute paths: Windows CreateProcess won't resolve relative ones with forward slashes
    binary, ffmpeg = (str(Path(a).resolve()) for a in sys.argv[1:3])
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        env = dict(os.environ, XDG_CONFIG_HOME=str(d / "cfg"), APPDATA=str(d / "cfg"))
        for src, target in make_files(d, ffmpeg):
            r = subprocess.run([binary, "--crush", str(src), "--nogui", "--target", str(target)],
                               env=env, capture_output=True, text=True, timeout=600)
            outs = [p for p in d.iterdir() if p.name.startswith(src.stem + "_crushed")]
            size = outs[0].stat().st_size if outs else 0
            good = r.returncode == 0 and outs and size <= target * 1_000_000
            ok &= bool(good)
            print(f"{'PASS' if good else 'FAIL'}  {src.name:<10} {src.stat().st_size/1e6:7.2f} MB -> "
                  f"{size/1e6:6.2f} MB (target {target} MB, exit {r.returncode})")
            if not good:
                print(r.stdout[-2000:], r.stderr[-2000:], sep="\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
