$ProcessesToLimit = @("msedge", "chrome")

while ($true) {
    foreach ($ProcName in $ProcessesToLimit) {
        $Procs = Get-Process -Name $ProcName -ErrorAction SilentlyContinue
        
        if ($Procs) {
            foreach ($Proc in $Procs) {
                # If priority is Normal or higher, reduce it
                if ($Proc.PriorityClass -eq 'Normal' -or $Proc.PriorityClass -eq 'High') {
                    try {
                        $Proc.PriorityClass = 'BelowNormal'
                    } catch {
                        # Silently ignore access denied
                    }
                }
            }
        }
    }
    Start-Sleep -Seconds 60
}
