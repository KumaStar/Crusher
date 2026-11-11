<div align="center">

<img src="crusher.png" width="96" alt="Crusher icon">

# Crusher

**Make any file small enough to send.**
Right-click a file, click **Crush**, done. Perfect for Discord, email and WhatsApp limits.

[**⬇ Windows**](https://github.com/KumaStar/Crusher/releases/latest) &nbsp;·&nbsp;
[**⬇ macOS**](https://github.com/KumaStar/Crusher/releases/latest) <sup>beta</sup> &nbsp;·&nbsp;
[**⬇ Linux**](https://github.com/KumaStar/Crusher/releases/latest) <sup>beta</sup>

<img src="docs/demo.gif" alt="Crusher shrinking a 44.7 MB video to 7.7 MB in a few seconds" width="500">

</div>

---

## Install

Everything it needs is included (FFmpeg too). No Python, no admin rights.
Pick your file from the [latest release](https://github.com/KumaStar/Crusher/releases/latest):

| System | Download | Install |
|---|---|---|
| **Windows** 10/11 | `Crusher-Setup.exe` | Double-click → **Install** |
| **macOS** Apple Silicon (M1–M4…) | `Crusher-mac-arm64.dmg` | Open it, drag **Crusher** into **Applications**, open Crusher once |
| **macOS** Intel | `Crusher-mac-intel.dmg` | Same as above |
| **Linux** (x86_64) | `Crusher-x86_64.AppImage` | Make it executable, then double-click it once |

<details>
<summary><b>Windows says "Windows protected your PC"</b></summary>

That warning shows up for new apps that aren't code-signed yet. Click **More info → Run anyway**.
</details>

<details>
<summary><b>macOS says "Crusher can't be opened" / "Apple could not verify…"</b></summary>

Crusher isn't signed with a paid Apple developer certificate yet, so macOS blocks the first launch.

1. Click **Done** (not "Move to Trash").
2. Open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to Crusher.
3. Open Crusher again and confirm.

You only need to do this once.
</details>

<details>
<summary><b>Linux: how to make the AppImage executable</b></summary>

Right-click the file → **Properties → Permissions** → tick **Allow executing file as program**. Or in a terminal:

```sh
chmod +x Crusher-x86_64.AppImage
./Crusher-x86_64.AppImage
```

Keep the AppImage somewhere permanent (for example `~/Applications`). If you move it later, open it once and the menus update themselves.
</details>

> macOS and Linux versions are **beta**: they're built and tested automatically, but haven't had many real users yet.
> If something doesn't work, please [open an issue](https://github.com/KumaStar/Crusher/issues).

## How to use

### From the right-click menu (fastest)

Opening Crusher once adds it to your right-click menu.

| System | Where to find it |
|---|---|
| **Windows 11** | Right-click → **Show more options** (or **Shift** + right-click) → **Crusher → Crush to target size** |
| **Windows 10** | Right-click → **Crusher → Crush to target size** |
| **macOS** | Right-click in Finder → **Quick Actions → Crush with Crusher** (it may be under **Services** on older macOS) |
| **Linux: GNOME Files** | Right-click → **Scripts → Crush with Crusher** |
| **Linux: KDE Dolphin** | Right-click → **Actions → Crush with Crusher** |
| **Linux: Cinnamon Nemo** | Right-click → **Crush with Crusher** |

On Linux you can also right-click a video, picture or document → **Open With → Crusher**.

A new file appears next to the original, named like `holiday_video_crushed.mp4`.
**Your original file is never changed.**

### From the app

Open **Crusher** (Start menu, Applications folder or app menu), click **Browse…**, choose a file, set the size you want, and press **Crush**.

<img src="docs/app.png" alt="Crusher window with a video loaded and the target set to 8 MB" width="420">

When it finishes, you get a summary:

<img src="docs/done.png" alt="Done dialog: 44.67 MB to 7.68 MB, 83% smaller" width="200">

### Picking a size

The default target is **8 MB**. Common limits:

| Where you're sending it | Set the target to |
|---|---|
| Discord (free account) | 10 MB |
| Email (Gmail, Outlook) | 20 MB |

Drag the slider or type a number in the app. To change the default for each file type, click ⚙.

## What it can shrink

| File type | Examples | What happens |
|---|---|---|
| 🎬 Video | mp4, mov, mkv, avi, webm… | Re-encoded to fit. Lowers resolution only if it has to |
| 🎵 Audio | mp3, wav, flac, m4a… | Converted to MP3 at the best quality that fits |
| 🖼 Image | jpg, png, webp, bmp, tiff | Best quality that fits. Transparency is kept |
| 🎞 GIF | gif | Fewer colours or frames until it fits |
| 📄 PDF | pdf | Pictures inside get smaller. Text stays sharp |
| 📝 Office | docx, pptx, xlsx, epub… | Pictures inside get smaller. The file still opens normally |
| 📦 Anything else | * | Packed into a ZIP |

Files already under the target are left alone. If something can't get under the target, you still get the smallest version possible, marked **Best effort**.

## Uninstall

- **Windows**: **Settings → Apps → Installed apps → Crusher → Uninstall.** This also removes the right-click menu.
- **macOS / Linux**: in Crusher, click ⚙ and untick **Right-click menu**, then **Save**. Then delete the app (drag Crusher from Applications to the Trash, or delete the AppImage).

---

## For developers

<details open>
<summary><b>Run from source</b></summary>

Requires Python 3.9+ and FFmpeg (`winget install Gyan.FFmpeg`, or set the folder in ⚙ Settings).

```powershell
git clone https://github.com/KumaStar/Crusher.git
cd Crusher
py -m pip install -r requirements.txt     # customtkinter, Pillow, pikepdf (+ optional pillow-heif)
py app.py                                 # open the app
```

macOS / Linux: `python3 -m pip install -r requirements.txt` and `python3 app.py`. FFmpeg: `brew install ffmpeg` / your distro's package.

Add the right-click menu for the source checkout (per user, no admin):

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1
powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1 -Uninstall
```

```sh
# macOS / Linux
python3 app.py --integrate        # Finder Quick Action, or GNOME/KDE/Nemo actions + .desktop entry
python3 app.py --unintegrate
```

</details>

<details>
<summary><b>Command line</b></summary>

```powershell
py app.py "file.pdf"                              # open with a file loaded
py app.py --crush "file.mp4"                      # start immediately
py app.py --crush "file.wav" --nogui --target 5   # console only, 5 MB target
python -m crusher ...                             # same as app.py
```

`--nogui` exit codes: `0` done or skipped, `1` error, `2` best effort (over target), `130` cancelled.

</details>

<details>
<summary><b>How each engine works</b></summary>

| Type | Method |
|---|---|
| Video | 2-pass H.264 + AAC with bitrates calculated from the target. Resolution and frame rate drop when needed, and it re-encodes again if the result is still over |
| Audio | MP3 at the highest bitrate that fits |
| GIF | Optimised palette, then lowers frame rate → colours → size |
| Image | Highest JPEG/WebP quality that fits, downscaled only if needed. Keeps alpha (PNG/WebP) |
| PDF | Lossless cleanup with pikepdf, then steps down embedded image size and quality |
| Office / eBook | Recompresses embedded pictures (same names and formats) and re-zips tighter |
| Other | Max-compression ZIP |

Sizes are strict: 1 MB = 1,000,000 bytes.

</details>

<details>
<summary><b>Settings</b></summary>

Stored in `%APPDATA%\Crusher\config.json` (`~/Library/Application Support/Crusher` on macOS, `~/.config/crusher` on Linux).

- Target per type: video, audio, GIF, image, PDF, Office, other
- Video max resolution and x264 speed preset
- File name suffix, output folder, FFmpeg folder

</details>

<details>
<summary><b>Build the installers</b></summary>

Every build bundles the app with PyInstaller and a static FFmpeg (downloaded once and cached under `installer/`).

| System | Command | Output |
|---|---|---|
| Windows | `.\build.ps1` (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)) | `installer\Output\Crusher-Setup.exe` |
| macOS | `./build.sh` | `release/Crusher-mac-arm64.dmg` or `-intel.dmg` |
| Linux x86_64 | `./build.sh` | `release/Crusher-x86_64.AppImage` |

Test a build: `python scripts/smoke_test.py <built binary> <ffmpeg>` crushes a generated video, image, PDF and text file and checks that each one fits.

**Releasing:** push a version tag. GitHub Actions builds all four packages on Windows, macOS (Apple Silicon + Intel) and Ubuntu, smoke-tests each one, and publishes them in one release. Tags with a dash become pre-releases.

```sh
git tag v1.1.0-beta.1 && git push --tags   # pre-release
git tag v1.1.0 && git push --tags          # release
```

</details>

<details>
<summary><b>Project layout</b></summary>

```
app.py                    launcher used by the right-click menu and the exe
crusher/
  core.py                 config, FFmpeg lookup, Job (progress/cancel/ffmpeg runner). No UI, cross-platform
  engines/                one module per file type: analyze() / preview() / crush()
  gui.py                  CustomTkinter desktop window
  integrate.py            macOS Quick Action / Linux file-manager actions (set up on first launch)
  __main__.py             CLI and entry point
installer/crusher.iss     Inno Setup script (Windows shortcuts + right-click menu)
build.ps1                 Windows build: PyInstaller + FFmpeg + installer
build.sh                  macOS (.dmg) and Linux (.AppImage) build
packaging/linux/          AppImage entry point and .desktop file
scripts/smoke_test.py     end-to-end test of a built binary
install_context_menu.ps1  Windows right-click menu for source checkouts
docs/                     README images
```

</details>

<details>
<summary><b>Roadmap: Android</b></summary>

Tk doesn't run on Android, and ffmpeg-kit (the usual way to ship FFmpeg in a Python Android app) was retired in 2025.
The likely route is a small native app that appears in the **Share** menu, using Android's built-in encoders (Media3 Transformer) for video and audio and Bitmap compression for images. It would follow the same rules as the engines here (target size in, smallest file that fits out).

Also on the list: Apple code signing and notarization (removes the "Open Anyway" step), Linux arm64, and a Flatpak.

</details>

## License and credits

- Crusher is released under the [MIT License](LICENSE).
- The installer bundles [FFmpeg](https://ffmpeg.org) (GPL build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)), which Crusher runs as a separate program.
