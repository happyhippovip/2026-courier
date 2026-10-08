param(
    [string]$OutDir = "$PSScriptRoot\dist",
    # Newest CPython 3.12 embeddable amd64 zip published on python.org
    # (verified 2026-10-07). Later 3.12 tags on the FTP are source-only.
    # Must satisfy pyproject.toml requires-python (>=3.12,<3.13).
    [string]$PythonVersion = "3.12.10"
)

# Decided package architecture: C# launcher + embeddable CPython.
# PyInstaller onedir and Inno Setup are not used.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "Building Courier Windows Package (embedded Python $PythonVersion)..."
if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required to install the package runtime into libs."
    exit 1
}

# 1. Build Native Launcher
& "$PSScriptRoot\launcher\build_launcher.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build Courier.exe"
    exit 1
}

$projectRoot = (Resolve-Path "$PSScriptRoot\..\..\").Path

# 2. Copy binaries, installer scripts, and every installable product package.
Copy-Item "$PSScriptRoot\Courier.exe" -Destination $OutDir
Copy-Item "$PSScriptRoot\install.ps1" -Destination $OutDir
Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir

# Keep this list equal to the on-disk packages selected by
# [tool.setuptools.packages.find].include. The launcher starts
# courier_core, courier_worker and courier_hub from this set.
$RuntimePackages = @(
    "adapters",
    "courier_core",
    "courier_hub",
    "courier_overlay",
    "courier_runtime",
    "courier_worker"
)

foreach ($pkg in $RuntimePackages) {
    $src = Join-Path $projectRoot $pkg
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Error "Runtime package not found: $src"
        exit 1
    }
    Copy-Item -LiteralPath $src -Destination (Join-Path $OutDir $pkg) -Recurse -Force
}

# 3. Download and embed Python. The ._pth name is the file that CPython
# actually reads (python312._pth for 3.12.x).
# SHA256 of python-3.12.10-embed-amd64.zip, package "CPython" in
# python-3.12.10-embed-amd64.zip.spdx.json published next to the zip.
$PythonSha256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$pyZip = Join-Path $env:TEMP "courier-python-embed.zip"
Write-Host "Downloading Embedded Python from $PythonUrl..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip
$actualHash = (Get-FileHash -Algorithm SHA256 -Path $pyZip).Hash
if ($actualHash.ToLowerInvariant() -ne $PythonSha256.ToLowerInvariant()) {
    Write-Error "Embedded Python zip hash mismatch. Expected $PythonSha256 got $actualHash"
    exit 1
}
$pyDir = Join-Path $OutDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Write-Host "Extracting Python..."
Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force

$pthName = "python312._pth"
$pyTag = "python{0}{1}" -f $PythonVersion.Split(".")[0], $PythonVersion.Split(".")[1]
if ($pthName -ne "$pyTag._pth") {
    Write-Error "Pth file $pthName does not match embedded Python $PythonVersion"
    exit 1
}
$pthPath = Join-Path $pyDir $pthName
if (-not (Test-Path -LiteralPath $pthPath)) {
    Write-Error "Embedded distribution is missing $pthName"
    exit 1
}
# Paths are relative to the python directory. ".." is the package root
# (staged packages). "..\libs" is the dependency target. import site stays
# commented so the embed does not pick up the machine's site-packages.
Add-Content -Path $pthPath -Encoding ascii -Value ".."
Add-Content -Path $pthPath -Encoding ascii -Value "..\libs"

$pythonExe = Join-Path $pyDir "python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Error "Embedded python.exe missing after extract"
    exit 1
}

Write-Host "Installing project and dependencies with the embedded interpreter..."
uv pip install --python "$pythonExe" --target "$OutDir\libs" "$projectRoot"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install Courier runtime into libs"
    exit 1
}

# 4. Create ZIP package
$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"
if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
Write-Host "Zipping package to $zipOut..."
Compress-Archive -Path "$OutDir\*" -DestinationPath $zipOut

Write-Host "Done! Package is ready at $zipOut"
