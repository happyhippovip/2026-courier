$task = Get-ScheduledTask -TaskName WindowsAIOSWorker
$task | Format-List
$task.Triggers | Format-List
$task.Actions | Format-List
