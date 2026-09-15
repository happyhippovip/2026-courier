Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*worker.ps1*" -or $_.CommandLine -like "*autonomy.ps1*" } | Select-Object ProcessId, CreationDate, CommandLine | Format-List
