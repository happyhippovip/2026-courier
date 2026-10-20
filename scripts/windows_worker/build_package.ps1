param(
    [string]$OutDir = "$PSScriptRoot\dist",
    [string]$PythonUrl = "https://www.python.org/ftp/python/3.12.6/python-3.12.6-embed-amd64.zip"
)

Write-Host "Building Courier Windows Package..."
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

# 2. Copy binaries and scripts
Copy-Item "$PSScriptRoot\Courier.exe" -Destination $OutDir
Copy-Item "$PSScriptRoot\daemon.py" -Destination $OutDir
Copy-Item "$PSScriptRoot\bootstrap.ps1" -Destination $OutDir
Copy-Item "$PSScriptRoot\install.ps1" -Destination $OutDir
Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir
Copy-Item -Recurse "$PSScriptRoot\..\..\courier_worker" -Destination "$OutDir\courier_worker"
if (Test-Path "$PSScriptRoot\..\..\adapters") {
    Copy-Item -Recurse "$PSScriptRoot\..\..\adapters" -Destination "$OutDir\adapters"
}

# V49c Policy & R1 Integration: Ensure policy and observer modules are bundled
$scriptsDir = Join-Path $OutDir "scripts"
New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null
Copy-Item "$PSScriptRoot\..\resource_policy.py" -Destination $scriptsDir
if (Test-Path "$PSScriptRoot\..\inbound_response_observer.py") {
    Copy-Item "$PSScriptRoot\..\inbound_response_observer.py" -Destination $scriptsDir
}
if (Test-Path "$PSScriptRoot\..\invoice_generator.py") {
    Copy-Item "$PSScriptRoot\..\invoice_generator.py" -Destination $scriptsDir
}

# Policy JSON definition
$policiesDir = Join-Path $OutDir "events\policies"
New-Item -ItemType Directory -Force -Path $policiesDir | Out-Null
if (Test-Path "$PSScriptRoot\..\..\events\policies\resource_policy.json") {
    Copy-Item "$PSScriptRoot\..\..\events\policies\resource_policy.json" -Destination $policiesDir
}

# 3. Download and embed Python
$pyZip = "$env:TEMP\python-embed.zip"
Write-Host "Downloading Embedded Python from $PythonUrl..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip
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
