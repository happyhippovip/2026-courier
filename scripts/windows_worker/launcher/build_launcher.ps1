param()
Write-Host "Compiling Courier Launcher..."
$csc = "$env:windir\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-Not (Test-Path $csc)) {
    $csc = "$env:windir\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
& $csc /target:winexe /out:"$PSScriptRoot\..\Courier.exe" "$PSScriptRoot\CourierLauncher.cs"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success: Courier.exe built."
} else {
    Write-Error "Failed to build Courier Launcher."
}
