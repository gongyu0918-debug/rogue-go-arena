param(
    [string]$Version = (Get-Date -Format "yyyy.MM.dd")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistDir = Join-Path $RepoRoot "dist"
$ReleaseDir = Join-Path $RepoRoot "release"

function Resolve-Iscc {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }
    throw "ISCC.exe not found. Please install Inno Setup 6 first."
}

Write-Host "==> Repo root: $RepoRoot"
Write-Host "==> Build version: $Version"

if (Test-Path $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}
if (Test-Path (Join-Path $RepoRoot "build")) {
    Remove-Item -LiteralPath (Join-Path $RepoRoot "build") -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

Write-Host "==> Building launcher EXE"
python -m PyInstaller --noconfirm GoAI.spec

Write-Host "==> Building server EXE bundle"
python -m PyInstaller --noconfirm GoAI_Server.spec

$iscc = Resolve-Iscc
Write-Host "==> Building installer with Inno Setup"
& $iscc `
    "/DMyAppVersion=$Version" `
    "/DRepoRoot=$RepoRoot" `
    "/DReleaseDir=$ReleaseDir" `
    (Join-Path $RepoRoot "GoAI_Setup.iss")

Write-Host "==> Build completed"
Get-ChildItem $ReleaseDir | Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
