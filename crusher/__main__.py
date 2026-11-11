"""Entry point:  python -m crusher [file] [--crush FILE] [--target MB] [--nogui]"""
from __future__ import annotations

import argparse
import os
import sys

from . import engines, integrate
from .core import KIND_LABELS, Cancelled, CrushError, Job, fmt_size, fmt_time, load_config, save_config


def run_cli(path: str, cfg: dict, target: float | None) -> int:
    info = None
    try:
        info = engines.analyze(path, cfg)
    except CrushError as e:
        print(f"Error: {e}")
        return 1
    target = target or cfg["targets"][info.kind]
    print(f"{KIND_LABELS[info.kind]}: {info.summary}")
    last = [-1]

    def prog(f, text):
        pct = int(f * 100)
        if pct != last[0]:
            last[0] = pct
            print(f"\r{text[:50]:<50} {pct:3d}%", end="", flush=True)

    job = Job(path, target, cfg, prog)
    try:
        r = engines.crush(job, info)
    except (KeyboardInterrupt, Cancelled):
        job.cancel()
        print("\nCancelled.")
        return 130
    except CrushError as e:
        print(f"\nError: {e}")
        return 1
    print()
    if r.skipped:
        print(f"Already under {target:g} MB ({fmt_size(r.src_size)}), nothing to do.")
        return 0
    flag = "  (best effort, over target)" if r.missed else ""
    print(f"{fmt_size(r.src_size)} -> {fmt_size(r.out_size)}  [{r.detail}]  in {fmt_time(r.elapsed)}{flag}")
    print(r.out)
    return 2 if r.missed else 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # None under pythonw
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(prog="crusher", description="Crush files to a target size.")
    ap.add_argument("file", nargs="?", help="file to load")
    ap.add_argument("--crush", metavar="FILE", help="start crushing FILE immediately")
    ap.add_argument("--target", type=float, help="target size in MB (overrides settings)")
    ap.add_argument("--nogui", action="store_true", help="console only (use with --crush)")
    ap.add_argument("--integrate", action="store_true", help="add the right-click menu (macOS/Linux)")
    ap.add_argument("--unintegrate", action="store_true", help="remove the right-click menu (macOS/Linux)")
    args = ap.parse_args()
    cfg = load_config()
    if args.integrate or args.unintegrate:
        return run_integrate(cfg, add=args.integrate)
    path = args.crush or args.file
    if path and not os.path.isfile(path):
        print(f"File not found: {path}", file=sys.stderr)
        if args.nogui:
            return 2
        path = None
    if args.nogui:
        if not path:
            ap.error("--nogui needs a file (e.g. --crush file.mp4 --nogui)")
        return run_cli(path, cfg, args.target)
    integrate.sync(cfg, save_config)
    from .gui import run_gui
    run_gui(cfg, path, auto=bool(args.crush and path), target=args.target)
    return 0


def run_integrate(cfg: dict, add: bool) -> int:
    if not integrate.SUPPORTED:
        print("On Windows the right-click menu comes from the installer "
              "(or install_context_menu.ps1 for a source checkout).")
        return 1
    if add:
        integrate.install()
        cfg["shell_integration"] = integrate.launch_id()
    else:
        integrate.uninstall()
        cfg["shell_integration"] = "off"
    save_config(cfg)
    for p in integrate.paths():
        print(("+ " if add else "- ") + str(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
