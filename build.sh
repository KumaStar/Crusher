#!/usr/bin/env bash
# Builds Crusher for macOS (.dmg) or Linux (.AppImage), with FFmpeg bundled.
# Output goes to release/. Windows uses build.ps1 instead.
#   ./build.sh            build for this machine
#   PYTHON=python3.12 ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
OS="$(uname -s)"
ARCH="$(uname -m)"                 # arm64 | x86_64
CACHE="installer/ffmpeg-${OS}-${ARCH}"
mkdir -p release "$CACHE"

echo "==> Python deps"
"$PY" -m pip install --upgrade -r requirements.txt pyinstaller

# ----------------------------------------------------------------------------- FFmpeg
fetch_ffmpeg() {
  [[ -x "$CACHE/ffmpeg" && -x "$CACHE/ffprobe" ]] && return
  echo "==> Downloading FFmpeg for $OS $ARCH"
  local tmp; tmp="$(mktemp -d)"
  if [[ "$OS" == "Darwin" ]]; then
    local plat; plat=$([[ "$ARCH" == "arm64" ]] && echo arm64 || echo amd64)
    # "latest" redirect only exists for ffmpeg.zip; ffprobe.zip sits in the same release folder
    local url; url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' \
      "https://ffmpeg.martin-riedl.de/redirect/latest/macos/${plat}/release/ffmpeg.zip")"
    curl -fsSL "$url" -o "$tmp/ffmpeg.zip"
    curl -fsSL "${url%/ffmpeg.zip}/ffprobe.zip" -o "$tmp/ffprobe.zip"
    unzip -oq "$tmp/ffmpeg.zip" -d "$CACHE"
    unzip -oq "$tmp/ffprobe.zip" -d "$CACHE"
  else
    [[ "$ARCH" == "x86_64" ]] || { echo "Linux build supports x86_64 only for now"; exit 1; }
    curl -fsSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o "$tmp/ff.tar.xz"
    tar -xJf "$tmp/ff.tar.xz" -C "$tmp"
    cp "$tmp"/ffmpeg-*-static/ffmpeg "$tmp"/ffmpeg-*-static/ffprobe "$CACHE/"
  fi
  chmod +x "$CACHE/ffmpeg" "$CACHE/ffprobe"
  rm -rf "$tmp"
}
fetch_ffmpeg

# ----------------------------------------------------------------------------- PyInstaller
COMMON=(--noconfirm --clean --windowed --name Crusher
        --add-data "crusher.png:." --add-data "crusher.ico:."
        --collect-all customtkinter)

if [[ "$OS" == "Darwin" ]]; then
  echo "==> Icon"
  ICONSET="build/crusher.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s crusher.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2)); sips -z $d $d crusher.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o build/crusher.icns

  echo "==> PyInstaller"
  "$PY" -m PyInstaller "${COMMON[@]}" --icon build/crusher.icns \
    --osx-bundle-identifier com.kumastar.crusher app.py

  APP="dist/Crusher.app"
  cp "$CACHE/ffmpeg" "$CACHE/ffprobe" "$APP/Contents/MacOS/"
  # adding files breaks PyInstaller's ad-hoc signature; re-sign so Apple Silicon will launch it
  codesign --force --deep --sign - "$APP"

  echo "==> DMG"
  NAME=$([[ "$ARCH" == "arm64" ]] && echo "Crusher-mac-arm64" || echo "Crusher-mac-intel")
  STAGE="build/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  rm -f "release/$NAME.dmg"
  hdiutil create -volname "Crusher" -srcfolder "$STAGE" -ov -format UDZO "release/$NAME.dmg" >/dev/null
  echo "Done: release/$NAME.dmg"
else
  echo "==> PyInstaller"
  "$PY" -m PyInstaller "${COMMON[@]}" app.py
  cp "$CACHE/ffmpeg" "$CACHE/ffprobe" dist/Crusher/

  echo "==> AppImage"
  APPDIR="build/Crusher.AppDir"; rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr"
  cp -R dist/Crusher "$APPDIR/usr/bin"
  cp packaging/linux/AppRun "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
  cp packaging/linux/crusher.desktop "$APPDIR/crusher.desktop"
  cp crusher.png "$APPDIR/crusher.png"

  TOOL="installer/appimagetool-x86_64.AppImage"
  if [[ ! -x "$TOOL" ]]; then
    curl -fsSL https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -o "$TOOL"
    chmod +x "$TOOL"
  fi
  # extract-and-run: works without FUSE (CI runners, containers, WSL)
  APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" release/Crusher-x86_64.AppImage
  echo "Done: release/Crusher-x86_64.AppImage"
fi
