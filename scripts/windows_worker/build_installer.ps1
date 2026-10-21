# Courier Symphony - Windows Installer Packaging Script
# Compiles CourierSetup-v1.exe via Inno Setup (ISCC.exe)
# Supports clean per-user installation and automated verification

param(
    [switch]$VerifyInstall = $false,
    [string]$OutExe = "$PSScriptRoot\CourierSetup-v1.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Courier Symphony: Windows Installer Build ==="

# 1. Locate ISCC.exe
$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe",
    "$env:ProgramFiles (x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
)

$isccPath = $null
foreach ($cand in $isccCandidates) {
    if ($cand -and (Test-Path $cand)) {
        $isccPath = $cand
        break
    }
}

if (-not $isccPath) {
    Write-Error "BUILD FAILED: Inno Setup Compiler (ISCC.exe) not found."
    exit 1
}

Write-Host "Using Inno Setup compiler: $isccPath"

# 2. Check Prerequisites
$issPath = "$PSScriptRoot\courier_installer.iss"
if (-not (Test-Path $issPath)) {
    Write-Error "BUILD FAILED: Installer script '$issPath' not found."
    exit 1
}

$distDir = "$PSScriptRoot\dist"
if (-not (Test-Path $distDir)) {
    Write-Host "Dist directory missing. Running build_package.ps1 first..."
    & "$PSScriptRoot\build_package.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD FAILED: build_package.ps1 returned code $LASTEXITCODE"
        exit 1
    }
}

# 3. Compile Installer
Write-Host "Compiling installer via Inno Setup..."
$compileProcess = Start-Process -FilePath $isccPath -ArgumentList "`"$issPath`"" -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru -Wait
if ($compileProcess.ExitCode -ne 0) {
    Write-Error "COMPILATION FAILED: ISCC exited with code $($compileProcess.ExitCode)"
    exit 1
}

if (-not (Test-Path $OutExe)) {
    Write-Error "BUILD FAILED: Expected installer '$OutExe' was not produced."
    exit 1
}

$hash = (Get-FileHash -Algorithm SHA256 $OutExe).Hash
$size = (Get-Item $OutExe).Length
Write-Host "BUILD SUCCESS: $OutExe"
Write-Host "Size:   $size bytes"
Write-Host "SHA256: $hash"

# 4. Optional Verification
if ($VerifyInstall) {
    Write-Host "`n=== Verifying Clean Silent Install and Uninstall ==="
    $installDir = "$env:LOCALAPPDATA\CourierWorker"
    if (Test-Path $installDir) {
        Remove-Item -Recurse -Force $installDir
    }

    Write-Host "Executing silent install..."
    $instProc = Start-Process -FilePath $OutExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -PassThru -Wait
    if ($instProc.ExitCode -ne 0) {
        Write-Error "VERIFICATION FAILED: Silent installation exited with code $($instProc.ExitCode)"
        exit 1
    }

    $targetExe = "$installDir\Courier.exe"
    $uninstaller = "$installDir\unins000.exe"
    if (-not (Test-Path $targetExe)) {
        Write-Error "VERIFICATION FAILED: Installed Courier.exe not found at $targetExe"
        exit 1
    }
    if (-not (Test-Path $uninstaller)) {
        Write-Error "VERIFICATION FAILED: Installed uninstaller not found at $uninstaller"
        exit 1
    }
    Write-Host "Silent installation verified successfully."

    Write-Host "Executing silent uninstall..."
    $uninstProc = Start-Process -FilePath $uninstaller -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -PassThru -Wait
    if ($uninstProc.ExitCode -ne 0) {
        Write-Error "VERIFICATION FAILED: Silent uninstallation exited with code $($uninstProc.ExitCode)"
        exit 1
    }

    if (Test-Path $targetExe) {
        Write-Error "VERIFICATION FAILED: Target executable still present after uninstall."
        exit 1
    }
    Write-Host "Silent uninstallation verified successfully."
    Write-Host "=== Clean Machine Lifecycle PASSED ==="
}
