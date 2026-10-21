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

Copy-Item "$PSScriptRoot\install_service.ps1" -Destination $OutDir

Copy-Item "$PSScriptRoot\uninstall.ps1" -Destination $OutDir

Copy-Item "$PSScriptRoot\status.bat" -Destination $OutDir

Copy-Item "$PSScriptRoot\stop.bat" -Destination $OutDir

Copy-Item -Recurse "$PSScriptRoot\..\..\courier_worker" -Destination "$OutDir\courier_worker"

if (Test-Path "$PSScriptRoot\..\..\adapters") {

    Copy-Item -Recurse "$PSScriptRoot\..\..\adapters" -Destination "$OutDir\adapters"

}



# V49c Policy & R1 Integration: Ensure mandatory policy and observer modules are bundled (W05 / GB-PKG-05)

$scriptsDir = Join-Path $OutDir "scripts"

New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null

$policyPy = "$PSScriptRoot\..\resource_policy.py"
if (-not (Test-Path -LiteralPath $policyPy)) {
    Write-Error "BUILD_FAIL: Mandatory policy script '$policyPy' does not exist."
    exit 1
}
Copy-Item -LiteralPath $policyPy -Destination $scriptsDir

if (Test-Path "$PSScriptRoot\..\inbound_response_observer.py") {

    Copy-Item "$PSScriptRoot\..\inbound_response_observer.py" -Destination $scriptsDir

}

if (Test-Path "$PSScriptRoot\..\invoice_generator.py") {

    Copy-Item "$PSScriptRoot\..\invoice_generator.py" -Destination $scriptsDir

}



# Policy JSON definition (Mandatory Policy Bundling - W05)

$policiesDir = Join-Path $OutDir "events\policies"

New-Item -ItemType Directory -Force -Path $policiesDir | Out-Null

$policyJson = "$PSScriptRoot\..\..\events\policies\resource_policy.json"
if (-not (Test-Path -LiteralPath $policyJson)) {
    Write-Error "BUILD_FAIL: Mandatory policy definition '$policyJson' does not exist."
    exit 1
}
Copy-Item -LiteralPath $policyJson -Destination $policiesDir



# 3. Download and embed Python

$pyZip = "$env:TEMP\python-embed.zip"

$expectedPySha = "A86A2E28870967745D255CC597D1E4D19AE79E65E927CDC324BAA0256202231C"

$needsDownload = $true

if (Test-Path $pyZip) {

    try {

        $existingHash = (Get-FileHash -Path $pyZip -Algorithm SHA256).Hash.ToUpper()

        if ($existingHash -eq $expectedPySha) {

            Write-Host "Using cached Embedded Python with verified SHA256 ($existingHash)..."

            $needsDownload = $false

        } else {

            Write-Warning "Cached python-embed.zip hash mismatch ($existingHash vs $expectedPySha), redownloading..."

        }

    } catch {

        Write-Warning "Error hashing cached python-embed.zip, redownloading..."

    }

}



if ($needsDownload) {

    Write-Host "Downloading Embedded Python from $PythonUrl..."

    $origPref = $ProgressPreference

    try {

        $ProgressPreference = 'SilentlyContinue'

        Invoke-WebRequest -Uri $PythonUrl -OutFile $pyZip

    } finally {

        $ProgressPreference = $origPref

    }

    $downloadedHash = (Get-FileHash -Path $pyZip -Algorithm SHA256).Hash.ToUpper()

    if ($downloadedHash -ne $expectedPySha) {

        Write-Error "Security Error: Embedded Python SHA256 checksum mismatch ($downloadedHash vs $expectedPySha)"

        exit 1

    }

}



$pyDir = Join-Path $OutDir "python"

New-Item -ItemType Directory -Force -Path $pyDir | Out-Null

Write-Host "Extracting Python..."

Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force

Add-Content -Path "$pyDir\python312._pth" -Value ".."



Write-Host "Installing dependencies using uv..."

$projectRoot = (Resolve-Path "$PSScriptRoot\..\..\").Path

uv pip install --target "$OutDir\libs" "$projectRoot"

Add-Content -Path "$pyDir\python312._pth" -Value "..\libs"



# 3c. Generate Cryptographic Package Manifest (W04 / GB-PKG-04)
Write-Host "Generating package manifest (manifest.json)..."
$manifestFile = Join-Path $OutDir "manifest.json"
if (Test-Path -LiteralPath $manifestFile) {
    Remove-Item -LiteralPath $manifestFile -Force
}

$filesDict = [ordered]@{}
$allFiles = Get-ChildItem -LiteralPath $OutDir -Recurse | Where-Object { -not $_.PSIsContainer } | Sort-Object FullName
foreach ($file in $allFiles) {
    $relPath = $file.FullName.Substring($OutDir.Length).TrimStart('\', '/')
    if ($relPath -eq "manifest.json") { continue }
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToUpper()
    $filesDict[$relPath] = [ordered]@{
        size   = $file.Length
        sha256 = $hash
    }
}

$manifest = [ordered]@{
    manifest_version = "1.0"
    algorithm        = "SHA256"
    package_name     = "CourierWorker-Windows"
    file_count       = $filesDict.Count
    files            = $filesDict
}

$manifestJson = $manifest | ConvertTo-Json -Depth 10
Set-Content -LiteralPath $manifestFile -Value $manifestJson -Encoding UTF8
Write-Host "Package manifest generated with $($filesDict.Count) files."

# 3b. Verify Package Integrity using smoke_package.ps1

if (Test-Path "$PSScriptRoot\smoke_package.ps1") {

    Write-Host "Running pre-zip smoke verification..."

    & "$PSScriptRoot\smoke_package.ps1" -PackageDir "$OutDir" -RequireManifest

    if ($LASTEXITCODE -ne 0) {

        Write-Error "Pre-zip smoke verification failed!"

        exit 1

    }

}



# 4. Create ZIP package

$zipOut = "$PSScriptRoot\CourierWorker-v1.zip"

if (Test-Path $zipOut) { Remove-Item -Force $zipOut }

Write-Host "Zipping package to $zipOut..."

Compress-Archive -Path "$OutDir\*" -DestinationPath "$zipOut"



Write-Host "Done! Package is ready at $zipOut"

