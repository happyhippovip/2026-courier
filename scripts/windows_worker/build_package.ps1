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
# Excluded internal fleet files: adapters
# if (Test-Path "$PSScriptRoot\..\..\adapters") {
#     Copy-Item -Recurse "$PSScriptRoot\..\..\adapters" -Destination "$OutDir\adapters"
# }
Copy-Item -Recurse "$PSScriptRoot\..\..\server" -Destination "$OutDir\server"
if (Test-Path "$OutDir\server\state") { Remove-Item -Recurse -Force "$OutDir\server\state" }
Copy-Item -Recurse "$PSScriptRoot\..\..\courier_core" -Destination "$OutDir\courier_core"
if (Test-Path "$PSScriptRoot\..\..\static") {
    Copy-Item -Recurse "$PSScriptRoot\..\..\static" -Destination "$OutDir\static"
}
# Excluded internal fleet files: studio
# if (Test-Path "$PSScriptRoot\..\..\studio") {
#     Copy-Item -Recurse "$PSScriptRoot\..\..\studio" -Destination "$OutDir\studio"
# }

# Copy-Item "$PSScriptRoot\install.ps1" -Destination $OutDir -ErrorAction SilentlyContinue
# Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$OutDir\scripts" | Out-Null
Copy-Item "$PSScriptRoot\..\*.py" -Destination "$OutDir\scripts\"
New-Item -ItemType File -Force -Path "$OutDir\scripts\__init__.py" | Out-Null
Get-ChildItem -Path $OutDir -Recurse -Filter "test_*.py" | Remove-Item -Force

# 3. Download and embed Python
$pyZip = "$env:TEMP\python-embed.zip"
if (-not (Test-Path $pyZip)) {
    Write-Host "Downloading Embedded Python from $PythonUrl..."
    Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip
}
$pyDir = Join-Path $OutDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Write-Host "Extracting Python..."
Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force

# Enable site packages in embedded python
$pthFile = "$pyDir\python311._pth"
$pthContent = Get-Content $pthFile
$pthContent = $pthContent -replace '#import site', 'import site'
$pthContent += ".."
Set-Content -Path $pthFile -Value $pthContent

Write-Host "Installing dependencies..."
$getPipPath = "$env:TEMP\get-pip.py"
if (-not (Test-Path $getPipPath)) {
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath
}
& "$pyDir\python.exe" $getPipPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install pip"
    exit 1
}

# Install project dependencies
& "$pyDir\python.exe" -m pip install flask==3.1.3 requests==2.34.2 psutil==7.2.2 pywebview==6.2.1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install pip dependencies"
    exit 1
}

Write-Host "Installing dependencies using uv..."
$projectRoot = (Resolve-Path "$PSScriptRoot\..\..\").Path
uv pip install --target "$OutDir\libs" $projectRoot
Add-Content -Path "$pyDir\python311._pth" -Value "..\libs"

# 4. Create ZIP package
$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"
if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
Write-Host "Zipping package to $zipOut..."
Compress-Archive -Path "$OutDir\*" -DestinationPath $zipOut

Write-Host "Done! Package is ready at $zipOut"
