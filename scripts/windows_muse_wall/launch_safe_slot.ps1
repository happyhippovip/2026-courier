#Requires -Version 5.1
<# Explicit opt-in: relocate Muse data for this child only, never credentials.
   DataHome must already exist on an independently validated ancestor chain.
   Muse remains responsible for sandbox admission; this does not bypass it.
   No arbitrary flags, shell expressions, global environment or ACL changes. #>
param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$DataHome
)
$ErrorActionPreference = 'Stop'
foreach ($path in @($Workspace, $DataHome)) {
    if (-not [IO.Path]::IsPathRooted($path) -or
        -not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "An existing absolute directory is required: $path"
    }
}
# Capture BEFORE any throwing lookup: if Get-Command fails, finally must not
# clobber pre-existing parent values with $null assignments.
$previousData = $env:XDG_DATA_HOME
$previousUpdate = $env:MUSE_NO_AUTO_UPDATE
$previousLogin = $env:MUSE_LOGIN
$museCommand = Get-Command muse -ErrorAction Stop
function Restore-SlotEnvValue {
    # $Previous is deliberately untyped: a missing variable arrives as $null
    # and must be UNSET again, never stored back as an empty string.
    param($Name, $Previous)
    if ($null -eq $Previous) {
        Remove-Item "Env:\$Name" -ErrorAction SilentlyContinue
    } else {
        Set-Item "Env:\$Name" -Value $Previous
    }
}
try {
    $env:XDG_DATA_HOME = (Get-Item -LiteralPath $DataHome).FullName
    $env:MUSE_NO_AUTO_UPDATE = '1'
    $env:MUSE_LOGIN = '0'
    & $museCommand --disable-approval --workspace (Get-Item -LiteralPath $Workspace).FullName
} finally {
    Restore-SlotEnvValue 'XDG_DATA_HOME' $previousData
    Restore-SlotEnvValue 'MUSE_NO_AUTO_UPDATE' $previousUpdate
    Restore-SlotEnvValue 'MUSE_LOGIN' $previousLogin
}
