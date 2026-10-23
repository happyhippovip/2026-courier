# Courier Symphony - Windows installer packaging script.
# Compiles CourierSetup-v1.exe with Inno Setup 6 (ISCC.exe).
# -VerifyInstall changes the current user's profile. Leave it off unless that
# profile is a disposable Windows session you are allowed to modify.
# This host does not download ISCC. A missing compiler is a failed build.

param(
    [switch]$VerifyInstall = $false,
    [string]$OutExe = "$PSScriptRoot\CourierSetup-v1.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Courier Symphony: Windows Installer Build ==="

$isccCandidates = @(
    "$env:ProgramFiles (x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
)

$isccPath = $null
foreach ($cand in $isccCandidates) {
    if ($cand -and (Test-Path -LiteralPath $cand)) {
        $isccPath = $cand
        break
    }
}

if (-not $isccPath) {
    Write-Error "BUILD FAILED: Inno Setup Compiler (ISCC.exe) not found. No compiler was downloaded."
    exit 1
}

Write-Host "Using Inno Setup compiler: $isccPath"

$issPath = Join-Path $PSScriptRoot "courier_installer.iss"
if (-not (Test-Path -LiteralPath $issPath)) {
    Write-Error "BUILD FAILED: Installer script '$issPath' not found."
    exit 1
}

$distDir = Join-Path $PSScriptRoot "dist"
if (-not (Test-Path -LiteralPath $distDir)) {
    Write-Host "Dist directory missing. Running build_package.ps1 first..."
    & (Join-Path $PSScriptRoot "build_package.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "BUILD FAILED: build_package.ps1 returned code $LASTEXITCODE"
        exit 1
    }
}

Write-Host "Compiling installer via Inno Setup..."
$compileProcess = Start-Process -FilePath $isccPath -ArgumentList "`"$issPath`"" -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru -Wait
if ($compileProcess.ExitCode -ne 0) {
    Write-Error "COMPILATION FAILED: ISCC exited with code $($compileProcess.ExitCode)"
    exit 1
}

if (-not (Test-Path -LiteralPath $OutExe)) {
    Write-Error "BUILD FAILED: Expected installer '$OutExe' was not produced."
    exit 1
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutExe).Hash
$size = (Get-Item -LiteralPath $OutExe).Length
Write-Host "BUILD SUCCESS: $OutExe"
Write-Host "Size:   $size bytes"
Write-Host "SHA256: $hash"

if ($VerifyInstall) {
    Write-Host ""
    Write-Host "=== Verifying silent install and uninstall ==="
    $installDir = Join-Path $env:LOCALAPPDATA "Programs\Courier"
    $dataDir = Join-Path $env:LOCALAPPDATA "Courier"
    if ($installDir -eq $dataDir) {
        Write-Error "VERIFICATION REFUSED: install directory is the data directory."
        exit 1
    }
    $dataExisted = Test-Path -LiteralPath $dataDir
    $dbPath = Join-Path $dataDir "courier.db"
    $dbExisted = Test-Path -LiteralPath $dbPath

    if (Test-Path -LiteralPath $installDir) {
        Remove-Item -LiteralPath $installDir -Recurse -Force
    }

    Write-Host "Executing silent install..."
    $instProc = Start-Process -FilePath $OutExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG" -PassThru -Wait
    if ($instProc.ExitCode -ne 0) {
        Write-Error "VERIFICATION FAILED: Silent installation exited with code $($instProc.ExitCode)"
        exit 1
    }

    $targetExe = Join-Path $installDir "Courier.exe"
    $uninstaller = Join-Path $installDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $targetExe)) {
        Write-Error "VERIFICATION FAILED: Installed Courier.exe not found at $targetExe"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $uninstaller)) {
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

    if (Test-Path -LiteralPath $targetExe) {
        Write-Error "VERIFICATION FAILED: Target executable still present after uninstall."
        exit 1
    }
    if ($dataExisted -and -not (Test-Path -LiteralPath $dataDir)) {
        Write-Error "VERIFICATION FAILED: data directory was removed."
        exit 1
    }
    if ($dbExisted -and -not (Test-Path -LiteralPath $dbPath)) {
        Write-Error "VERIFICATION FAILED: courier.db was removed."
        exit 1
    }
    Write-Host "Silent uninstallation verified successfully."
}
