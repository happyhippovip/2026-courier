# Remove Courier credentials from user profiles.
# Database and logs stay unless -RemoveUserData is set.
param(
    [Parameter(Mandatory = $true)][string]$UsersRoot,
    [switch]$RemoveUserData,
    [switch]$IncludeEnvironment
)

$ErrorActionPreference = "Continue"

function Clear-OneCourierDir {
    param([string]$CourierDir)
    if (-not (Test-Path -LiteralPath $CourierDir)) { return }
    if ($RemoveUserData) {
        Remove-Item -LiteralPath $CourierDir -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $CourierDir) {
            Write-Output "ERROR: user data is still present at $CourierDir."
            $script:failed = $true
            return
        }
        Write-Output "Removed user data: $CourierDir"
        return
    }
    $blocked = $false
    foreach ($name in @("config.json", "run")) {
        $path = Join-Path $CourierDir $name
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $path) {
                Write-Output "ERROR: credential path is still present at $path."
                $script:failed = $true
                $blocked = $true
            }
        }
    }
    if ($blocked) { return }
    Write-Output "Removed credentials from $CourierDir. Database and logs were preserved."
}

$script:failed = $false

if (Test-Path -LiteralPath $UsersRoot) {
    Get-ChildItem -LiteralPath $UsersRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Clear-OneCourierDir (Join-Path $_.FullName "AppData\Local\Courier")
    }
} else {
    Write-Output "No user profiles at $UsersRoot."
}

if ($IncludeEnvironment) {
    if ($env:LOCALAPPDATA) {
        Clear-OneCourierDir (Join-Path $env:LOCALAPPDATA "Courier")
    }
    if ($env:COURIER_HOME) {
        Clear-OneCourierDir $env:COURIER_HOME
    }
}

if ($script:failed) { exit 1 }
exit 0
