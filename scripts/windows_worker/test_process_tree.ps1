Write-Host "Building package to get dist folder..."
cd C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker
.\build_package.ps1

Write-Host "Starting Courier.exe..."
$proc = Start-Process -FilePath ".\dist\Courier.exe" -PassThru
$procId = $proc.Id
Write-Host "Courier.exe started with PID $procId"

Start-Sleep -Seconds 10

Write-Host "Capturing process tree using WMI..."
# Define function to get child processes
function Get-ChildProcesses {
    param([int]$ParentId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId"
    foreach ($child in $children) {
        Write-Output $child
        Get-ChildProcesses -ParentId $child.ProcessId
    }
}

$tree = Get-ChildProcesses -ParentId $procId
Write-Host "--- Process Tree ---"
Write-Host "Root: Courier.exe (PID: $procId)"
foreach ($p in $tree) {
    Write-Host "  |- $($p.Name) (PID: $($p.ProcessId)) - CommandLine: $($p.CommandLine)"
}
Write-Host "--------------------"

Write-Host "Cleaning up..."
Stop-Process -Id $procId -Force
