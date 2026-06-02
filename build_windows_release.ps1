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

function Enable-PythonWmiGuard {
    $guardDir = Join-Path $env:TEMP "rogue-go-arena-py-wmi-guard"
    New-Item -ItemType Directory -Force -Path $guardDir | Out-Null
    @'
import platform

def _skip_wmi_query(*args, **kwargs):
    raise OSError("WMI query skipped during release build")

if hasattr(platform, "_wmi_query"):
    platform._wmi_query = _skip_wmi_query
'@ | Set-Content -LiteralPath (Join-Path $guardDir "sitecustomize.py") -Encoding UTF8

    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$guardDir;$env:PYTHONPATH"
    } else {
        $env:PYTHONPATH = $guardDir
    }
}

function Test-ReleaseKataGoAssets {
    $katagoDir = Join-Path $RepoRoot "katago"
    $engineNames = @("katago_cuda.exe", "katago.exe", "katago_opencl.exe", "katago_cpu.exe")
    $modelNames = @("model_large.bin.gz", "model.bin.gz", "model_b18.bin.gz")
    $engines = @($engineNames | Where-Object { Test-Path (Join-Path $katagoDir $_) })
    $models = @($modelNames | Where-Object { Test-Path (Join-Path $katagoDir $_) })

    if ($engines.Count -eq 0 -or $models.Count -eq 0) {
        $engineList = if ($engines.Count) { $engines -join ", " } else { "<none>" }
        $modelList = if ($models.Count) { $models -join ", " } else { "<none>" }
        throw (
            "KataGo release assets are incomplete. " +
            "Engines: $engineList; models: $modelList. " +
            "Run 'python setup.py' or place one supported engine and one supported model under '$katagoDir' before building."
        )
    }

    Write-Host "==> KataGo assets: engines=$($engines -join ', ') models=$($models -join ', ')"
}

function Assert-NativeCommandSucceeded {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Write-Host "==> Repo root: $RepoRoot"
Write-Host "==> Build version: $Version"
Write-Host "==> Build dir: $BuildDir"
Write-Host "==> Dist dir: $DistDir"
Write-Host "==> Release dir: $ReleaseDir"

Test-ReleaseKataGoAssets

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
$oldPythonPath = $env:PYTHONPATH
try {
    Enable-PythonWmiGuard

    $frontendPackage = Join-Path $RepoRoot "frontend\package.json"
    if (Test-Path $frontendPackage) {
        $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
        if (-not $npmCmd) {
            throw "npm not found. Install Node.js before building the React frontend."
        }

        Write-Host "==> Installing frontend dependencies"
        npm ci --prefix (Join-Path $RepoRoot "frontend")
        Assert-NativeCommandSucceeded "npm ci"

        Write-Host "==> Building React frontend"
        npm run build --prefix (Join-Path $RepoRoot "frontend")
        Assert-NativeCommandSucceeded "npm run build"
    }

    Write-Host "==> Building launcher EXE"
    python -m PyInstaller --noconfirm --distpath $DistDir --workpath $BuildDir rogue-go-arena.spec
    Assert-NativeCommandSucceeded "PyInstaller launcher build"

    Write-Host "==> Building server EXE bundle"
    python -m PyInstaller --noconfirm --distpath $DistDir --workpath $BuildDir rogue-go-arena-server.spec
    Assert-NativeCommandSucceeded "PyInstaller server build"

    $iscc = Resolve-Iscc
    Write-Host "==> Building installer with Inno Setup"
    & $iscc `
        "/DMyAppVersion=$Version" `
        "/DRepoRoot=$RepoRoot" `
        "/DDistDir=$DistDir" `
        "/DReleaseDir=$ReleaseDir" `
        (Join-Path $RepoRoot "rogue-go-arena_Setup.iss")
    Assert-NativeCommandSucceeded "Inno Setup compiler"
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}

Write-Host "==> Build completed"
Get-ChildItem $ReleaseDir | Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
