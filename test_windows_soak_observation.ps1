param (
    [int]$DurationSeconds = 20,
    [int]$IntervalSeconds = 5
)

Write-Host "--- WINDOWS SOAK OBSERVATION (Sampling over ${DurationSeconds}s) ---"

$TargetProcesses = @("Courier", "Code", "python", "msedge", "ChatGPT")

$Telemetry = @()

$Iterations = [math]::Ceiling($DurationSeconds / $IntervalSeconds)

for ($i = 1; $i -le $Iterations; $i++) {
    Write-Host "[Sample $i/$Iterations] Collecting telemetry..."
    
    $procs = Get-Process -Name $TargetProcesses -ErrorAction SilentlyContinue | Select-Object Name, Id, CPU, WorkingSet64, HandleCount, Threads
    
    foreach ($p in $procs) {
        $Telemetry += [PSCustomObject]@{
            Time        = (Get-Date)
            Iteration   = $i
            Name        = $p.Name
            Id          = $p.Id
            CPU         = $p.CPU
            WorkingSet  = $p.WorkingSet64
            HandleCount = $p.HandleCount
            ThreadCount = $p.Threads.Count
        }
    }
    
    if ($i -lt $Iterations) { Start-Sleep -Seconds $IntervalSeconds }
}

Write-Host "`n--- TREND EVIDENCE SUMMARY ---"

$grouped = $Telemetry | Group-Object Name

foreach ($group in $grouped) {
    $name = $group.Name
    
    $wsFirst = ($group.Group | Where-Object { $_.Iteration -eq 1 } | Measure-Object -Property WorkingSet -Sum).Sum
    $wsLast = ($group.Group | Where-Object { $_.Iteration -eq $Iterations } | Measure-Object -Property WorkingSet -Sum).Sum
    
    $hcFirst = ($group.Group | Where-Object { $_.Iteration -eq 1 } | Measure-Object -Property HandleCount -Sum).Sum
    $hcLast = ($group.Group | Where-Object { $_.Iteration -eq $Iterations } | Measure-Object -Property HandleCount -Sum).Sum
    
    $wsGrowth = if ($wsFirst -ne $null -and $wsLast -ne $null) { $wsLast - $wsFirst } else { 0 }
    $handleGrowth = if ($hcFirst -ne $null -and $hcLast -ne $null) { $hcLast - $hcFirst } else { 0 }
    
    $pCountFirst = ($group.Group | Where-Object { $_.Iteration -eq 1 }).Count
    $pCountLast = ($group.Group | Where-Object { $_.Iteration -eq $Iterations }).Count
    
    $cpuFirst = ($group.Group | Where-Object { $_.Iteration -eq 1 } | Measure-Object -Property CPU -Sum).Sum
    $cpuLast = ($group.Group | Where-Object { $_.Iteration -eq $Iterations } | Measure-Object -Property CPU -Sum).Sum
    $cpuDelta = if ($cpuFirst -ne $null -and $cpuLast -ne $null) { $cpuLast - $cpuFirst } else { 0 }

    Write-Host "`nProcess Group: $name"
    Write-Host "  Process Count : $pCountFirst -> $pCountLast"
    Write-Host "  Memory Growth : $([math]::Round($wsGrowth / 1MB, 2)) MB"
    Write-Host "  Handle Growth : $handleGrowth"
    Write-Host "  CPU Delta     : $([math]::Round($cpuDelta, 2)) sec"
    
    if ($wsGrowth -gt 50MB) { Write-Host "  [!] Warning: High memory growth detected." -ForegroundColor Yellow }
    if ($handleGrowth -gt 100) { Write-Host "  [!] Warning: Handle leak suspected." -ForegroundColor Yellow }
    if ($pCountFirst -ne $pCountLast) { Write-Host "  [!] Warning: Process count unstable (storm or crash loop)." -ForegroundColor Yellow }
    if ($cpuDelta -gt 10) { Write-Host "  [!] Warning: High CPU burn (Hot Idle potential)." -ForegroundColor Yellow }
}

Write-Host "`n--- OBSERVATION COMPLETE ---"
