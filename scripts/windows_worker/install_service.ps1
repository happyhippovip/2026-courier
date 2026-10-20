# Requires Run as Administrator
$action = "Create"
$taskName = "CourierWindowsWorker"
$scriptPath = "$PSScriptRoot\Courier.exe"

# Ensure SYSTEM profile has config and token synced from ProgramData or LocalAppData
$systemProfileData = "$env:SystemRoot\system32\config\systemprofile\AppData\Local\Courier"
$progDataDir = "$env:ProgramData\CourierWorker"
$progConfig = Join-Path $progDataDir "config.json"
$localConfig = "$env:LOCALAPPDATA\Courier\config.json"

if (Test-Path (Split-Path $systemProfileData)) {
    New-Item -ItemType Directory -Force -Path $systemProfileData -ErrorAction SilentlyContinue | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $systemProfileData "run") -ErrorAction SilentlyContinue | Out-Null

    $sourceConfig = ""
    if (Test-Path $progConfig) { $sourceConfig = $progConfig }
    elseif (Test-Path $localConfig) { $sourceConfig = $localConfig }

    if ($sourceConfig) {
        Copy-Item $sourceConfig -Destination (Join-Path $systemProfileData "config.json") -Force
        try {
            $parsed = Get-Content $sourceConfig | ConvertFrom-Json
            if ($parsed.COURIER_API_KEY) {
                $parsed.COURIER_API_KEY | Set-Content (Join-Path $systemProfileData "run\controller.token") -NoNewline
            }
        } catch { }
    }
}


if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered existing task."
}

$trigger = New-ScheduledTaskTrigger -AtStartup
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $PSScriptRoot
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal
Write-Host "Courier Windows Worker scheduled task registered to start on boot."
