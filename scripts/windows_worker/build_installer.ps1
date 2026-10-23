# Courier Symphony - Windows installer packaging script.
# Compiles CourierSetup-v1.exe with Inno Setup 6 (ISCC.exe).
# -VerifyInstall changes the current user's profile. Leave it off unless that
# profile is a disposable Windows session you are allowed to modify.
# ISCC is installed only when COURIER_INSTALL_INNO=1. The installer is Inno
# Setup 6.7.0 from the jrsoftware release, and the SHA256 below must match.

param(
    [switch]$VerifyInstall = $false,
    [string]$OutExe = "$PSScriptRoot\CourierSetup-v1.exe"
)

$ErrorActionPreference = "Stop"

$PinnedInnoVersion = "6.7.0"
$PinnedInnoSha256 = "F45C7D68D1E660CF13877EC36738A5179CE72A33414F9959D35E99B68C52A697"
$PinnedInnoUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_0/innosetup-6.7.0.exe"

function Find-Iscc {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
    )
    foreach ($cand in $candidates) {
        if ($cand -and (Test-Path -LiteralPath $cand)) {
            return $cand
        }
    }
    return $null
}

function Install-PinnedInnoSetup {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $destDir = Join-Path $env:TEMP "courier-inno-$PinnedInnoVersion"
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    $installer = Join-Path $destDir "innosetup-$PinnedInnoVersion.exe"
    Write-Host "Downloading pinned Inno Setup $PinnedInnoVersion"
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $PinnedInnoUrl -OutFile $installer -UseBasicParsing
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
    if ($actual -ne $PinnedInnoSha256) {
        Write-Error "BUILD FAILED: Inno Setup hash $actual does not match $PinnedInnoSha256"
        exit 1
    }
    Write-Host "Pinned Inno Setup hash matches $PinnedInnoSha256"
    $proc = Start-Process -FilePath $installer -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-" -PassThru -Wait
    if ($proc.ExitCode -ne 0) {
        Write-Error "BUILD FAILED: Inno Setup installer exited with code $($proc.ExitCode)"
        exit 1
    }
}

Write-Host "=== Courier Symphony: Windows Installer Build ==="

$isccPath = Find-Iscc
if (-not $isccPath -and $env:COURIER_INSTALL_INNO -eq "1") {
    Install-PinnedInnoSetup
    $isccPath = Find-Iscc
}

if (-not $isccPath) {
    Write-Error "BUILD FAILED: Inno Setup Compiler (ISCC.exe) not found. Set COURIER_INSTALL_INNO=1 to install pinned Inno Setup $PinnedInnoVersion."
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
    Write-Host "=== Verifying rollback, silent install, upgrade, and uninstall ==="
    $installDir = Join-Path $env:LOCALAPPDATA "Programs\Courier"
    $dataDir = Join-Path $env:LOCALAPPDATA "Courier"
    if ($installDir -eq $dataDir) {
        Write-Error "VERIFICATION REFUSED: install directory is the data directory."
        exit 1
    }
    $programsRoot = Split-Path -Parent $installDir
    New-Item -ItemType Directory -Force -Path $programsRoot | Out-Null
    if (Test-Path -LiteralPath $installDir) {
        Remove-Item -LiteralPath $installDir -Recurse -Force
    }

    # A file where the program directory must be created forces the setup to
    # fail before it can leave Courier.exe behind.
    Set-Content -LiteralPath $installDir -Value "block" -Encoding ascii
    Write-Host "Executing blocked install for rollback..."
    $blocked = Start-Process -FilePath $OutExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG" -PassThru -Wait
    $blockedItem = Get-Item -LiteralPath $installDir -ErrorAction SilentlyContinue
    if ($blocked.ExitCode -eq 0 -or -not $blockedItem -or $blockedItem.PSIsContainer) {
        Write-Error "ROLLBACK FAILED: blocked install exit=$($blocked.ExitCode) container=$($blockedItem.PSIsContainer)"
        exit 1
    }
    Remove-Item -LiteralPath $installDir -Force
    if (Test-Path -LiteralPath $installDir) {
        Write-Error "ROLLBACK FAILED: install directory still exists after the blocked install."
        exit 1
    }
    Write-Host "CLEAN MACHINE: $installDir was absent before the setup EXE ran."

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
    $programsMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $shortcut = Get-ChildItem -LiteralPath $programsMenu -Recurse -Filter "*.lnk" |
        Where-Object { $_.BaseName -eq "Courier Symphony" } |
        Select-Object -First 1
    if (-not $shortcut) {
        Write-Error "VERIFICATION FAILED: Start menu shortcut Courier Symphony.lnk was not created."
        exit 1
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcutTarget = $shell.CreateShortcut($shortcut.FullName).TargetPath
    if (-not [string]::Equals($shortcutTarget, $targetExe, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "VERIFICATION FAILED: Start menu shortcut target '$shortcutTarget' is not '$targetExe'."
        exit 1
    }
    Write-Host "Silent installation and Start menu shortcut verified."

    Write-Host "Executing silent upgrade over the existing install..."
    $upgrade = Start-Process -FilePath $OutExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG" -PassThru -Wait
    if ($upgrade.ExitCode -ne 0) {
        Write-Error "VERIFICATION FAILED: Silent upgrade exited with code $($upgrade.ExitCode)"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $targetExe)) {
        Write-Error "VERIFICATION FAILED: Courier.exe missing after upgrade."
        exit 1
    }
    Write-Host "Silent upgrade verified."

    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    $dbPath = Join-Path $dataDir "courier.db"
    Set-Content -LiteralPath $dbPath -Value "preserve" -Encoding ascii

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
    if (-not (Test-Path -LiteralPath $dataDir)) {
        Write-Error "VERIFICATION FAILED: data directory was removed."
        exit 1
    }
    if (-not (Test-Path -LiteralPath $dbPath)) {
        Write-Error "VERIFICATION FAILED: courier.db was removed."
        exit 1
    }
    Write-Host "Silent uninstallation verified successfully."
}
