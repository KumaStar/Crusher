"""Right-click menu integration for macOS (Finder Quick Action) and Linux (file managers).

Windows is handled by the installer (installer/crusher.iss) or install_context_menu.ps1.
"""
from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .core import IS_WIN

IS_MAC = sys.platform == "darwin"
SUPPORTED = not IS_WIN
ASSETS = Path(__file__).resolve().parent.parent       # crusher.png lives here (source and bundled)
MENU_LABEL = "Crush with Crusher"

# Linux "Open with" types. Anything else still gets the right-click action.
MIME_TYPES = [
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm", "video/x-msvideo",
    "video/x-ms-wmv", "video/x-flv", "video/mp2t", "video/3gpp", "video/mpeg",
    "audio/mpeg", "audio/x-wav", "audio/wav", "audio/flac", "audio/mp4", "audio/aac",
    "audio/ogg", "audio/opus", "audio/x-ms-wma", "audio/x-aiff",
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff",
    "application/pdf", "application/epub+zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.spreadsheet",
]


# --------------------------------------------------------------------------- launch command
def launch_cmd() -> list[str]:
    """How to start this copy of Crusher, as argv without the file arguments."""
    if os.environ.get("APPIMAGE"):                       # Linux AppImage: its own path survives moves
        return [os.environ["APPIMAGE"]]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(ASSETS / "app.py")]     # running from source


def launch_id() -> str:
    """Stable string for the current launch command (stored in config to detect moves)."""
    return shlex.join(launch_cmd())


def _app_bundle() -> Path | None:
    """macOS: the enclosing Crusher.app, if running from one."""
    p = Path(sys.executable).resolve()
    for parent in p.parents:
        if parent.suffix == ".app":
            return parent
    return None


# --------------------------------------------------------------------------- macOS
def _mac_paths() -> list[Path]:
    return [Path.home() / "Library" / "Services" / f"{MENU_LABEL}.workflow"]


def _mac_shell_script() -> str:
    app = _app_bundle() if getattr(sys, "frozen", False) else None
    if app:   # `open -n` starts a separate window per file, like the Windows menu does
        run = f'open -n -a {shlex.quote(str(app))} --args --crush "$f"'
    else:
        run = f'{shlex.join(launch_cmd())} --crush "$f" >/dev/null 2>&1 &'
    return f'for f in "$@"; do\n  {run}\ndone\n'


def _mac_install() -> None:
    wf = _mac_paths()[0] / "Contents"
    wf.mkdir(parents=True, exist_ok=True)
    info = {
        "NSServices": [{
            "NSMenuItem": {"default": MENU_LABEL},
            "NSMessage": "runWorkflowAsService",
            "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
            "NSSendFileTypes": ["public.item"],
        }],
    }
    action = {
        "AMAccepts": {"Container": "List", "Optional": True, "Types": ["com.apple.cocoa.string"]},
        "AMActionVersion": "2.0.3",
        "AMApplication": ["Automator"],
        "AMParameterProperties": {"COMMAND_STRING": {}, "CheckedForUserDefaultShell": {},
                                  "inputMethod": {}, "shell": {}, "source": {}},
        "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
        "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
        "ActionName": "Run Shell Script",
        "ActionParameters": {
            "COMMAND_STRING": _mac_shell_script(),
            "CheckedForUserDefaultShell": True,
            "inputMethod": 1,            # pass input as arguments
            "shell": "/bin/zsh",
            "source": "",
        },
        "BundleIdentifier": "com.apple.RunShellScript",
        "CFBundleVersion": "2.0.3",
        "CanShowSelectedItemsWhenRun": False,
        "CanShowWhenRun": True,
        "Category": ["AMCategoryUtilities"],
        "Class Name": "RunShellScriptAction",
        "InputUUID": "6A4C1E0B-3F7D-4C2A-9E51-2B8D7A0C1F11",
        "OutputUUID": "8E2B5D1C-7A4F-4B3E-A6C9-0D1E2F3A4B22",
        "UUID": "1F3E5C7A-9B2D-4E6F-8A0C-3D5E7F9A1B33",
        "isViewVisible": True,
    }
    doc = {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [{"action": action}],
        "connectors": {},
        "workflowMetaData": {
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }
    with open(wf / "Info.plist", "wb") as f:
        plistlib.dump(info, f)
    with open(wf / "document.wflow", "wb") as f:
        plistlib.dump(doc, f)
    _run(["/System/Library/CoreServices/pbs", "-update"])   # refresh the Services menu


# --------------------------------------------------------------------------- Linux
def _xdg_data() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _linux_paths() -> list[Path]:
    d = _xdg_data()
    return [
        d / "applications" / "crusher.desktop",
        d / "nautilus" / "scripts" / MENU_LABEL,
        d / "kio" / "servicemenus" / "crusher.desktop",
        d / "nemo" / "actions" / "crusher.nemo_action",
        d / "crusher" / "crusher.png",
    ]


def _desktop_exec(args: list[str]) -> str:
    """Quote argv for an Exec= line (Desktop Entry spec)."""
    def q(a: str) -> str:
        if a.startswith("%"):
            return a
        for ch in ("\\", '"', "`", "$"):
            a = a.replace(ch, "\\" + ch)
        return f'"{a}"'
    return " ".join(q(a) for a in args)


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _linux_install() -> None:
    apps, nautilus, kde, nemo, icon = _linux_paths()
    cmd = launch_cmd()
    icon.parent.mkdir(parents=True, exist_ok=True)
    src_icon = ASSETS / "crusher.png"
    if src_icon.is_file():
        shutil.copyfile(src_icon, icon)

    _write(apps, "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Crusher",
        "Comment=Shrink any file to a target size",
        f"Exec={_desktop_exec(cmd + ['%f'])}",
        f"Icon={icon}",
        "Terminal=false",
        "Categories=Utility;AudioVideo;",
        "MimeType=" + ";".join(MIME_TYPES) + ";",
        "Actions=crush;",
        "",
        "[Desktop Action crush]",
        "Name=Crush to target size",
        f"Exec={_desktop_exec(cmd + ['--crush', '%f'])}",
        "",
    ]))

    _write(nautilus, "#!/bin/sh\n# Crusher: GNOME Files (Nautilus) right-click > Scripts\n"
                     'for f in "$@"; do\n'
                     f'  {shlex.join(cmd)} --crush "$f" >/dev/null 2>&1 &\n'
                     "done\n", executable=True)

    _write(kde, "\n".join([
        "[Desktop Entry]",
        "Type=Service",
        "MimeType=all/allfiles;",
        "X-KDE-ServiceTypes=KonqPopupMenu/Plugin",
        "Actions=crush;",
        "",
        "[Desktop Action crush]",
        f"Name={MENU_LABEL}",
        f"Icon={icon}",
        f"Exec={_desktop_exec(cmd + ['--crush', '%f'])}",
        "",
    ]), executable=True)   # KDE 6 only loads executable service menus

    _write(nemo, "\n".join([
        "[Nemo Action]",
        f"Name={MENU_LABEL}",
        "Comment=Shrink this file to the target size",
        f"Exec={_desktop_exec(cmd + ['--crush', '%F'])}",
        f"Icon-Name={icon}",
        "Selection=s",
        "Extensions=any;",
        "",
    ]))

    _run(["update-desktop-database", str(apps.parent)])


# --------------------------------------------------------------------------- public API
def _run(cmd: list[str]) -> None:
    """Best-effort helper command; missing tools are fine."""
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def paths() -> list[Path]:
    if IS_MAC:
        return _mac_paths()
    if SUPPORTED:
        return _linux_paths()
    return []


def is_installed() -> bool:
    return any(p.exists() for p in paths())


def install() -> bool:
    """Add the right-click menu for this user. Returns False where not supported."""
    if not SUPPORTED:
        return False
    if IS_MAC:
        _mac_install()
    else:
        _linux_install()
    return True


def uninstall() -> bool:
    if not SUPPORTED:
        return False
    for p in paths():
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    if not IS_MAC:
        _run(["update-desktop-database", str(_linux_paths()[0].parent)])
    return True


def sync(cfg: dict, save) -> None:
    """On launch of a bundled build: set up the menu the first time, and repoint it if the app moved.

    Respects the user's choice to remove it ("off"). `save` persists cfg.
    """
    if not SUPPORTED or not getattr(sys, "frozen", False):
        return
    state = cfg.get("shell_integration", "")
    current = launch_id()
    if state == "off" or state == current:
        return
    try:
        install()
    except OSError:
        return
    cfg["shell_integration"] = current
    save(cfg)
