<#
.SYNOPSIS
  Adds (or removes) the "Crusher" right-click menu for ALL files.
  Per-user (HKCU) - no admin rights needed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1
  powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1 -Uninstall
  powershell -ExecutionPolicy Bypass -File .\install_context_menu.ps1 -Python "C:\Python314\pythonw.exe"
#>
param(
    [switch]$Uninstall,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$hkcu = [Microsoft.Win32.Registry]::CurrentUser
$allFiles = "Software\Classes\*\shell\Crusher"
# keys written by older versions (per-extension)
$oldExts = ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".ts"

function Remove-Key($sub) {
    if ($hkcu.OpenSubKey($sub)) { $hkcu.DeleteSubKeyTree($sub) }
}

foreach ($e in $oldExts) { Remove-Key "Software\Classes\SystemFileAssociations\$e\shell\Crusher" }
Remove-Key $allFiles

if ($Uninstall) {
    Write-Host "Crusher context menu removed." -ForegroundColor Green
    exit 0
}

$app = Join-Path $PSScriptRoot "app.py"
if (-not (Test-Path -LiteralPath $app)) { throw "app.py not found next to this installer ($app)." }

if (-not $Python) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw "python not found on PATH. Pass -Python 'C:\path\to\pythonw.exe'." }
    $Python = Join-Path (Split-Path $py.Source) "pythonw.exe"
}
if (-not (Test-Path -LiteralPath $Python)) { throw "pythonw.exe not found at $Python" }

$ico = Join-Path $PSScriptRoot "crusher.ico"
$icon = if (Test-Path -LiteralPath $ico) { "`"$ico`"" } else { "`"$Python`",0" }

$root = $hkcu.CreateSubKey($allFiles)
$root.SetValue("MUIVerb", "Crusher")
$root.SetValue("SubCommands", "")
$root.SetValue("Icon", $icon)
$root.Close()

function Add-Verb($name, $label, $cmd) {
    $k = $hkcu.CreateSubKey("$allFiles\shell\$name")
    $k.SetValue("", $label)
    $k.Close()
    $c = $hkcu.CreateSubKey("$allFiles\shell\$name\command")
    $c.SetValue("", $cmd)
    $c.Close()
}

Add-Verb "1crush" "Crush to target size" "`"$Python`" `"$app`" --crush `"%1`""
Add-Verb "2open"  "Open in Crusher"      "`"$Python`" `"$app`" `"%1`""

Write-Host "Crusher context menu installed for all files." -ForegroundColor Green
Write-Host "Windows 11: right-click a file > 'Show more options' (or Shift+F10) > Crusher."
