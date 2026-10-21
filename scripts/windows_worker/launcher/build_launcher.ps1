param(
    [switch]$TestBuild,
    [string]$OutFile = "$PSScriptRoot\..\Courier.exe"
)
Write-Host "Compiling Courier Launcher..."
$csc = "$env:windir\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-Not (Test-Path $csc)) {
    $csc = "$env:windir\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}

$sourceFile = Join-Path $PSScriptRoot "CourierLauncher.cs"
$manifestFile = Join-Path $PSScriptRoot "Courier.manifest"

if ($TestBuild) {
    & $csc /target:winexe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$OutFile" "$sourceFile"
} else {
    & $csc /target:winexe "/win32manifest:$manifestFile" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$OutFile" "$sourceFile"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success: Courier.exe built."
} else {
    Write-Error "Failed to build Courier Launcher."
}
