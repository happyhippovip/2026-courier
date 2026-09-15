param(
    [string]$DispatchId
)
Write-Output "LOCAL_STEP_ERLEDIGT: JA"
Write-Output "GESAMTAUFGABE_ERLEDIGT: NEIN"
Write-Output "BLOCKER: NONE"
Write-Output "NÄCHSTER_SCHRITT: RECONCILE_GOALS"
Write-Output "Executing dispatch $DispatchId"
exit 0
