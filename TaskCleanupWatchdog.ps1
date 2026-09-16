$MaxRuntimeHours = 6

while ($true) {
    # Suche nach python oder uv Prozessen, die länger als MaxRuntimeHours laufen
    $Procs = Get-Process -Name "python", "uv", "cmd" -ErrorAction SilentlyContinue | Where-Object { 
        $_.StartTime -lt (Get-Date).AddHours(-$MaxRuntimeHours)
    }

    foreach ($Proc in $Procs) {
        try {
            # Überprüfe per WMI die CommandLine, um wichtige System-Prozesse (wie pythonw) auszuschließen
            $WmiProc = Get-CimInstance Win32_Process -Filter "ProcessId=$($Proc.Id)" -ErrorAction SilentlyContinue
            
            # Wir killen Prozesse, die in der IDE als hängende Tasks auftauchen
            if ($WmiProc.CommandLine -match "uv run" -or $WmiProc.CommandLine -match "python.exe") {
                Write-Host "Beende hängenden Prozess $($Proc.Name) (PID: $($Proc.Id)), da er länger als $MaxRuntimeHours Stunden läuft."
                Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # Ignorieren falls keine Rechte
        }
    }
    
    # Check every 1 hour
    Start-Sleep -Seconds 3600
}
