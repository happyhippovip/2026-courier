$apiKey = Read-Host "Enter COURIER_API_KEY for Server (will be stored securely for SYSTEM)" -AsSecureString
$apiPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey))

$verifierKey = Read-Host "Enter COURIER_VERIFIER_API_KEY for Server" -AsSecureString
$verifierPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($verifierKey))

if (-not [string]::IsNullOrWhiteSpace($apiPlain) -and -not [string]::IsNullOrWhiteSpace($verifierPlain)) {
    Write-Host "Storing Keys in SYSTEM Credential Manager..."
    $tempFile = Join-Path $env:TEMP "courier_server_keys.txt"
    "$apiPlain`n$verifierPlain" | Out-File -FilePath $tempFile -Encoding utf8 -NoNewline
    
    $storeCmd = "import keyring; lines=open(r'$tempFile', encoding='utf-8').read().splitlines(); keyring.set_password('courier_worker', 'courier_api_key', lines[0]); keyring.set_password('courier_worker', 'courier_verifier_api_key', lines[1])"
    $storeAction = New-ScheduledTaskAction -Execute "uv" -Argument "run python -c `"$storeCmd`"" -WorkingDirectory $PSScriptRoot
    $storePrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $taskNameStore = "CourierSystemKeyStore_ServerTemp"
    
    Register-ScheduledTask -TaskName $taskNameStore -Action $storeAction -Principal $storePrincipal -Force | Out-Null
    Start-ScheduledTask -TaskName $taskNameStore
    Start-Sleep -Seconds 5
    Unregister-ScheduledTask -TaskName $taskNameStore -Confirm:$false | Out-Null
    Remove-Item -Path $tempFile -Force
    Write-Host "Server keys securely stored for SYSTEM." -ForegroundColor Green
}

# Requires Run as Administrator
$action = "Create"
$taskName = "CourierServer"
$scriptPath = "$PSScriptRoot\start_server.bat"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered existing task."
}

$trigger = New-ScheduledTaskTrigger -AtStartup
$action = New-ScheduledTaskAction -Execute $scriptPath

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings
Write-Host "Courier Server scheduled task registered to start on boot as SYSTEM with restart throttling."
