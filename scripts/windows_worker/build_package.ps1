param(
    [string]$OutDir = "$PSScriptRoot\dist",
    [string]$PythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
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
Copy-Item -Recurse "$PSScriptRoot\..\..\courier_worker" -Destination "$OutDir\courier_worker"
if (Test-Path "$PSScriptRoot\..\..\adapters") {
    Copy-Item -Recurse "$PSScriptRoot\..\..\adapters" -Destination "$OutDir\adapters"
}
Copy-Item "$PSScriptRoot\install.ps1" -Destination $OutDir
Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir

# 3. Download and embed Python
$pyZip = "$env:TEMP\python-embed.zip"
Write-Host "Downloading Embedded Python from $PythonUrl..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip
$pyDir = Join-Path $OutDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Write-Host "Extracting Python..."
Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force
Add-Content -Path "$pyDir\python311._pth" -Value ".."

# 4. Create ZIP package
$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"
if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
Write-Host "Zipping package to $zipOut..."
Compress-Archive -Path "$OutDir\*" -DestinationPath $zipOut

Write-Host "Done! Package is ready at $zipOut"
