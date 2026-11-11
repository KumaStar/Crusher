# Crusher

Right-click almost any file → **Crusher** → it's squeezed under a target size (default **8 MB**).
The target is strict: 1 MB = 1,000,000 bytes, which is the safer definition.

## Download (Windows)

Get **`Crusher-Setup.exe`** from the [Releases](https://github.com/KumaStar/Crusher/releases) page, double-click it, and click Install.
Everything is included (FFmpeg too), no Python needed. The right-click menu is added automatically; uninstall from Windows Settings.

| Type | Extensions | How |
|---|---|---|
| **Video** | mp4 mov mkv avi webm m4v wmv flv ts mts 3gp mpg… | 2-pass H.264 + AAC with bitrates calculated from the target. Resolution and frame rate drop automatically when needed. Re-encodes again if over target |
| **Audio** | mp3 wav flac m4a aac ogg opus wma aiff… | MP3 at the highest bitrate that fits |
| **GIF** | gif | Optimised palette. Lowers frame rate → colours → size until it fits |
| **Image** | jpg png webp bmp tiff (+ heic/avif with `pillow-heif`) | Highest JPEG/WebP quality that fits, downscaled only if needed. Transparency is kept (PNG/WebP) |
| **PDF** | pdf | Lossless cleanup, then steps down embedded image size/quality. Text and vector graphics stay sharp |
| **Office / eBook** | docx pptx xlsx odt odp ods epub | Recompresses the pictures inside (same names and formats, so the file stays valid) and re-zips tighter |
| **Anything else** | * | Max-compression ZIP. Opens natively everywhere |

Files already under the target are left alone. If PDF, Office, image or ZIP can't reach the target,
you get the smallest result it could make, marked **Best effort**.

On Windows 11 the menu is under **Show more options** (or Shift + right-click).

**FFmpeg** is needed for video, audio and GIF. The installer includes it. When running from source, use any of these:
- `winget install Gyan.FFmpeg` / `choco install ffmpeg` / `scoop install ffmpeg`
- or point **⚙ Settings → FFmpeg folder** at a build from <https://www.gyan.dev/ffmpeg/builds/>.

## Developers: run from source

```powershell
py -m pip install -r requirements.txt          # customtkinter, Pillow, pikepdf
py app.py                                       # open the app
py app.py --crush "file.mp4"                    # start immediately
py app.py --crush "file.wav" --nogui --target 5 # console only
powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1      # right-click menu from source
powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1 -Uninstall
```

Build the installer yourself: install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then run `.\build.ps1`. Output: `installer\Output\Crusher-Setup.exe`.

## Credits and license

- Licensed under the [MIT License](LICENSE).
- The installer bundles **FFmpeg** (GPL build from gyan.dev). Source: <https://ffmpeg.org>. Crusher runs it as a separate program.

Output is saved next to the original as `name_crushed.ext`, or in the output folder you set.

## Settings

Click ⚙ in the app. Settings are stored in `%APPDATA%\Crusher\config.json`
(`~/Library/Application Support/Crusher` on macOS, `~/.config/crusher` on Linux).

- **Target per type**: video, audio, GIF, image, PDF, Office, other
- Video max resolution and x264 speed preset
- File name suffix, output folder, FFmpeg folder

## Layout

```
app.py                  launcher used by the right-click menu
crusher/
  core.py               config, tool lookup, Job (progress/cancel/ffmpeg runner) - no UI, cross-platform
  engines/              one small module per file type: analyze() / preview() / crush()
  gui.py                CustomTkinter desktop window
  __main__.py           CLI + entry point
install_context_menu.ps1, crusher.ico, make_icon.py
```

## macOS / Android later

- **macOS**: `core` + `engines` + `gui` already run there (`brew install ffmpeg python-tk`).
  What's missing is a Finder **Quick Action** (Automator → "Run Shell Script":
  `python3 /path/app.py --crush "$@"`) and an `.app` bundle (py2app or PyInstaller).
- **Android**: Tk doesn't run there. The plan is to keep `core` + `engines` and add a small touch UI
  (Kivy or BeeWare) that shows up in the **Share** menu, with FFmpeg bundled via ffmpeg-kit.
  The engines take a path and return a path, so they carry over as they are.
