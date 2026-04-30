param(
    [string]$Version = (Get-Date -Format "yyyy.MM.dd"),
    [string]$BuildDir = (Join-Path $PSScriptRoot "build"),
    [string]$DistDir = (Join-Path $PSScriptRoot "dist"),
    [string]$ReleaseDir = (Join-Path $PSScriptRoot "release")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

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
Write-Host "==> Build dir: $BuildDir"
Write-Host "==> Dist dir: $DistDir"
Write-Host "==> Release dir: $ReleaseDir"

if (Test-Path $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}
if (Test-Path $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

Push-Location $RepoRoot
try {
    Write-Host "==> Building launcher EXE"
    python -m PyInstaller --noconfirm --distpath $DistDir --workpath $BuildDir rogue-go-arena.spec

    Write-Host "==> Building server EXE bundle"
    python -m PyInstaller --noconfirm --distpath $DistDir --workpath $BuildDir rogue-go-arena-server.spec

    $iscc = Resolve-Iscc
    Write-Host "==> Building installer with Inno Setup"
    & $iscc `
        "/DMyAppVersion=$Version" `
        "/DRepoRoot=$RepoRoot" `
        "/DDistDir=$DistDir" `
        "/DReleaseDir=$ReleaseDir" `
        (Join-Path $RepoRoot "rogue-go-arena_Setup.iss")
}
finally {
    Pop-Location
}

Write-Host "==> Build completed"
Get-ChildItem $ReleaseDir | Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
