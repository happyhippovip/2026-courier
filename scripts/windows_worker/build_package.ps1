param(
    [string]$OutDir = "$PSScriptRoot\dist",
    # CPython 3.12 embeddable amd64 zip satisfying pyproject.toml requires-python (>=3.12,<3.13)
    [string]$PythonVersion = "3.12.10"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "Building Courier Windows Package (embedded Python $PythonVersion)..."
if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

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

# 3. Download and embed Python.
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
$pthPath = Join-Path $pyDir $pthName
if (-not (Test-Path -LiteralPath $pthPath)) {
    Write-Error "Embedded distribution is missing $pthName"
    exit 1
}
Add-Content -Path $pthPath -Encoding ascii -Value ".."
Add-Content -Path $pthPath -Encoding ascii -Value "..\libs"

$pythonExe = Join-Path $pyDir "python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Error "Embedded python.exe missing after extract"
    exit 1
}

Write-Host "Installing dependencies using uv..."
if (Get-Command "uv" -ErrorAction SilentlyContinue) {
    uv pip install --python "$pythonExe" --target "$OutDir\libs" "$projectRoot"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies with uv"
        exit 1
    }
} else {
    Write-Host "Note: uv not found on PATH. Runtime modules packaged directly in $OutDir."
}

# 4. Create ZIP package
$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"
if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
Write-Host "Zipping package to $zipOut..."
Compress-Archive -Path "$OutDir\*" -DestinationPath $zipOut

# 5. Compile Inno Setup Installer (if ISCC.exe is available)
$issPath = "$PSScriptRoot\courier_installer.iss"
if (Test-Path $issPath) {
    $isccPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    )
    $isccExe = $isccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if ($isccExe) {
        Write-Host "Compiling Inno Setup Installer using $isccExe..."
        & $isccExe "/O$PSScriptRoot" $issPath
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Success! CourierSetup-v1.exe compiled successfully."
        } else {
            Write-Error "ISCC compilation failed with exit code $LASTEXITCODE"
            exit 1
        }
    } else {
        Write-Host "Note: Inno Setup Compiler (ISCC.exe) not found. Standard zip package created at $zipOut."
    }
}

Write-Host "Done! Package is ready at $zipOut"
