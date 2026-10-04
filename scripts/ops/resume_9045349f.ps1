$ErrorActionPreference = "Stop"

$url = "http://localhost:8080/tasks/resolve_gate"
$body = @{
    task_id = "9045349f-54af-4f8f-8a37-ac50ee0fa399"
    decision = "RETRY"
} | ConvertTo-Json

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer dev-secret-key"
}

Write-Host "Resuming Mission 9045349f-54af-4f8f-8a37-ac50ee0fa399 via $url..."
try {
    $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -Headers $headers
    Write-Host "Success:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 3 | Write-Host
} catch {
    Write-Host "Failed to resume mission. Is the server running on port 8080?" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
