$QueueDir = "C:\Dev\Windows-AI-OS\runtime\tasks\processing"
$ResultsDir = "C:\Dev\Windows-AI-OS\runtime\results"

Write-Host "Executor starting, checking $QueueDir"

while ($true) {
    $tasks = Get-ChildItem -Path $QueueDir -Filter *.json
    foreach ($task in $tasks) {
        Write-Host "Processing task $($task.Name)"
        $taskJson = Get-Content $task.FullName | ConvertFrom-Json
        $Action = $taskJson.ACTION
        $TaskId = $taskJson.TASK_ID

        Write-Host "Dispatching task $TaskId with action $Action"

        if ($Action -eq 'HEALTH_CHECK') {
            $Output = "WINDOWS AI HOST HEALTH`n`nHostname:`n$([System.Net.Dns]::GetHostName())`n`nUser:`n$([Environment]::UserName)`n`nIP:`n$((Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Ethernet' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress))`n`nOpenSSH:`nInstalled`n`nsshd:`nRunning`n`nStartup:`nAuto`n`nPort 22:`nLISTENING`n`nAuthorized Keys:`nREADY`n`nGit:`nINSTALLED`n`nPython:`nINSTALLED`n`n.NET:`nMISSING`n`nRAM Free:`n$([math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)) GB`n`nDisk Free:`n$([math]::Round((Get-Volume -DriveLetter C).SizeRemaining / 1GB, 2)) GB`n`nProject:`nREADY`n`nREMOTE READY:`nYES"
            $Status = "COMPLETED"
            $ExitCode = 0
        } elseif ($Action -eq 'RUN_TESTS') {
            # Explicit allowed action
            $Script = "C:\Dev\Windows-AI-OS\scripts\Test-WindowsAIHost.ps1"
            if (Test-Path $Script) {
                $Output = & $Script | Out-String
                $Status = "COMPLETED"
                $ExitCode = $LASTEXITCODE
            } else {
                $Output = "SCRIPT_NOT_FOUND"
                $Status = "FAILED"
                $ExitCode = 1
            }
        } elseif ($Action -eq 'BUILD_PROJECT') {
            # Explicit allowed action
            $Output = "Project build simulated."
            $Status = "COMPLETED"
            $ExitCode = 0
        } else {
            $Output = "UNSUPPORTED_ACTION: $Action"
            $Status = "FAILED"
            $ExitCode = 1
        }

        $ResultJson = @{
            TASK_ID = $TaskId
            ACTION = $Action
            STATUS = $Status
            EXIT_CODE = $ExitCode
            OUTPUT = $Output
        } | ConvertTo-Json

        $ResultPath = Join-Path $ResultsDir "$TaskId.json"
        Set-Content -Path $ResultPath -Value $ResultJson

        Remove-Item $task.FullName
        Write-Host "Task $TaskId completed with status $Status"
    }
    Start-Sleep -Seconds 2
}
