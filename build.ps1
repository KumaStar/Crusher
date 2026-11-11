# Builds dist\Crusher\ (app + bundled FFmpeg) and installer\Output\Crusher-Setup.exe.
# Requires: Python 3.9+ on PATH, Inno Setup 6 (ISCC.exe), internet access for the first run.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ffDir = Join-Path $PSScriptRoot "installer\ffmpeg"
$ffUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# 1. Build deps and the app
python -m pip install --upgrade -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

python -m PyInstaller --noconfirm --clean --windowed --name Crusher `
    --icon crusher.ico `
    --add-data "crusher.ico;." `
    --collect-all customtkinter `
    app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# 2. Fetch FFmpeg (cached in installer\ffmpeg)
$ffExe = Join-Path $ffDir "ffmpeg.exe"
if (-not (Test-Path $ffExe)) {
    New-Item -ItemType Directory -Force -Path $ffDir | Out-Null
    $zip = Join-Path $ffDir "ffmpeg.zip"
    Invoke-WebRequest -Uri $ffUrl -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $ffDir -Force
    $bin = Get-ChildItem -Path $ffDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    Copy-Item (Join-Path $bin.DirectoryName "ffmpeg.exe"), (Join-Path $bin.DirectoryName "ffprobe.exe") -Destination $ffDir -Force
    Remove-Item $zip
}

# 3. Put FFmpeg next to Crusher.exe
Copy-Item (Join-Path $ffDir "ffmpeg.exe"), (Join-Path $ffDir "ffprobe.exe") -Destination "dist\Crusher" -Force

# 4. Build the installer
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install it from https://jrsoftware.org/isinfo.php" }
& $iscc "installer\crusher.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Write-Host "Done: installer\Output\Crusher-Setup.exe" -ForegroundColor Green
