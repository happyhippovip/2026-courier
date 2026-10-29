param(
    [string]$OutDir = "$PSScriptRoot\dist",
    [string]$PythonUrl = "https://www.python.org/ftp/python/3.12.6/python-3.12.6-embed-amd64.zip"
)

Write-Host "Building Courier Windows Package..."
$projectRoot = (Resolve-Path "$PSScriptRoot\..\..\").Path

# Pre-flight check: Refuse build if required files are missing (Fail-Closed)
$requiredPaths = @(
    "$PSScriptRoot\Courier.exe",
    "$PSScriptRoot\install.ps1",
    "$PSScriptRoot\uninstall.ps1",
    "$projectRoot\courier_core",
    "$projectRoot\courier_hub",
    "$projectRoot\courier_runtime",
    "$projectRoot\courier_worker",
    "$projectRoot\scripts\resource_policy.py",
    "$projectRoot\events\policies\resource_policy.json"
)

foreach ($req in $requiredPaths) {
    if (-not (Test-Path $req)) {
        Write-Error "BUILD REFUSED: Required component '$req' is missing. Aborting package build."
        exit 1
    }
}

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

# 2. Copy binaries, core modules, runtime, and policies
Copy-Item "$PSScriptRoot\Courier.exe" -Destination $OutDir
Copy-Item -Recurse "$projectRoot\courier_core" -Destination "$OutDir\courier_core"
Copy-Item -Recurse "$projectRoot\courier_hub" -Destination "$OutDir\courier_hub"
Copy-Item -Recurse "$projectRoot\courier_runtime" -Destination "$OutDir\courier_runtime"
Copy-Item -Recurse "$projectRoot\courier_worker" -Destination "$OutDir\courier_worker"

# Package scripts/resource_policy.py into scripts/
New-Item -ItemType Directory -Force -Path "$OutDir\scripts" | Out-Null
Copy-Item "$projectRoot\scripts\resource_policy.py" -Destination "$OutDir\scripts\resource_policy.py"
New-Item -ItemType File -Force -Path "$OutDir\scripts\__init__.py" | Out-Null

# Package events/policies/resource_policy.json (Fail-closed canonical policy)
New-Item -ItemType Directory -Force -Path "$OutDir\events\policies" | Out-Null
Copy-Item "$projectRoot\events\policies\resource_policy.json" -Destination "$OutDir\events\policies\resource_policy.json"

if (Test-Path "$projectRoot\adapters") {
    Copy-Item -Recurse "$projectRoot\adapters" -Destination "$OutDir\adapters"
}
Copy-Item "$PSScriptRoot\install.ps1" -Destination $OutDir
Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir
if (Test-Path "$PSScriptRoot\stop.ps1") { Copy-Item "$PSScriptRoot\stop.ps1" -Destination $OutDir }
if (Test-Path "$PSScriptRoot\stop.bat") { Copy-Item "$PSScriptRoot\stop.bat" -Destination $OutDir }
if (Test-Path "$PSScriptRoot\start.bat") { Copy-Item "$PSScriptRoot\start.bat" -Destination $OutDir }

# 3. Download and embed Python. The hash is the SHA-256 of the official
# python.org embeddable package whose MD5 is ae256f31ee4700eba679802233bff3e9.
$expectedPythonSha256 = "a86a2e28870967745d255cc597d1e4d19ae79e65e927cdc324baa0256202231c"
$pyZip = "$env:TEMP\python-embed.zip"
Write-Host "Downloading Embedded Python from $PythonUrl..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip
$actualPythonSha256 = (Get-FileHash -Algorithm SHA256 -Path $pyZip).Hash.ToLower()
if ($actualPythonSha256 -ne $expectedPythonSha256) {
    Remove-Item -Force $pyZip -ErrorAction SilentlyContinue
    Write-Error "BUILD REFUSED: embedded Python SHA-256 mismatch (got $actualPythonSha256)."
    exit 1
}
$pyDir = Join-Path $OutDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Write-Host "Extracting Python..."
Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force
Add-Content -Path "$pyDir\python312._pth" -Value ".."

Write-Host "Installing dependencies using uv..."
$projectRoot = (Resolve-Path "$PSScriptRoot\..\..\").Path
uv pip install --target "$OutDir\libs" $projectRoot
Add-Content -Path "$pyDir\python312._pth" -Value "..\libs"

# 4. Create ZIP package
$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"
if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
Write-Host "Zipping package to $zipOut..."
Compress-Archive -Path "$OutDir\*" -DestinationPath $zipOut

Write-Host "Done! Package is ready at $zipOut"
