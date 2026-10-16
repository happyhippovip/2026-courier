param()
Write-Host "Compiling Courier Launcher..."
$csc = "$env:windir\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-Not (Test-Path -LiteralPath $csc)) {
    $csc = "$env:windir\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
$out = Join-Path (Split-Path -Parent $PSScriptRoot) "Courier.exe"
if (-Not (Test-Path -LiteralPath $csc)) {
    Write-Error "Courier launcher build not proven: csc.exe was not found."
    exit 1
}
& $csc /target:winexe "/out:$out" "$PSScriptRoot\CourierLauncher.cs"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Courier launcher build not proven."
    exit 1
}
if (-Not (Test-Path -LiteralPath $out)) {
    Write-Error "Courier launcher build not proven: Courier.exe was not written."
    exit 1
}
Write-Host "Success: Courier.exe built."
exit 0
