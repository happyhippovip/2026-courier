# Start Courier.exe and record the process this install owns.
# A second start must not replace a live record with a new process.

function ConvertTo-CourierProcessStem {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { return "" }
    # Windows names a second python "python#1". That is still the same program.
    $cut = $Name.Split('#')[0].Trim()
    return [IO.Path]::GetFileNameWithoutExtension($cut)
}

function Test-CourierProcessName {
    param(
        [string]$Actual,
        [string]$Expected
    )
    $left = ConvertTo-CourierProcessStem $Actual
    $right = ConvertTo-CourierProcessStem $Expected
    return [bool]($left -and $right -and ($left -eq $right))
}

function Test-CourierStartTime {
    param(
        $Process,
        [string]$Stamp
    )
    if ([string]::IsNullOrWhiteSpace($Stamp)) { return $true }
    $expected = [datetime]::MinValue
    $parsed = [datetime]::TryParse(
        $Stamp.Trim(),
        [cultureinfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind,
        [ref]$expected)
    if (-not $parsed) { return $false }
    try {
        $actual = $Process.StartTime.ToUniversalTime()
        $delta = [math]::Abs(($actual - $expected.ToUniversalTime()).TotalSeconds)
    } catch {
        # A live process whose clock cannot be read is still the recorded one.
        return $true
    }
    return ($delta -le 2)
}

function Start-CourierWorker {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$PidFile,
        [string]$ExpectedName = "Courier",
        [string[]]$ArgumentList = @()
    )

    if (-not (Test-Path -LiteralPath $ExePath)) {
        Write-Output "ERROR: Courier.exe was not found."
        return 1
    }

    if (Test-Path -LiteralPath $PidFile) {
        $lines = @(Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue)
        $processId = 0
        $raw = ""
        if ($lines.Count -ge 1) { $raw = [string]$lines[0] }
        if ([int]::TryParse($raw.Trim(), [ref]$processId) -and $processId -gt 0) {
            $existing = Get-Process -Id $processId -ErrorAction SilentlyContinue
            $stamp = ""
            if ($lines.Count -ge 2) { $stamp = [string]$lines[1] }
            $sameName = $existing -and (Test-CourierProcessName -Actual $existing.ProcessName -Expected $ExpectedName)
            $sameStart = $existing -and (Test-CourierStartTime -Process $existing -Stamp $stamp)
            if ($sameName -and $sameStart) {
                Write-Output "Courier is already running."
                return 0
            }
        }
    }

    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $ExePath
        $info.WorkingDirectory = Split-Path -Parent $ExePath
        $info.UseShellExecute = $false
        $quoted = @()
        foreach ($arg in $ArgumentList) {
            if ($arg -match '\s') { $quoted += '"' + $arg.Replace('"', '\"') + '"' }
            else { $quoted += $arg }
        }
        $info.Arguments = ($quoted -join ' ')
        $started = [System.Diagnostics.Process]::Start($info)
        if (-not $started) { throw "start returned no process" }
    } catch {
        Write-Output "ERROR: Courier did not start."
        return 1
    }

    $stamp = ""
    try { $stamp = $started.StartTime.ToUniversalTime().ToString("o") } catch { $stamp = "" }
    @($started.Id, $stamp) | Set-Content -LiteralPath $PidFile -Encoding ascii
    Write-Output "Started Courier."
    return 0
}

if ($MyInvocation.InvocationName -ne '.') {
    $code = Start-CourierWorker -ExePath (Join-Path $PSScriptRoot "Courier.exe") -PidFile (Join-Path $PSScriptRoot "worker.pid")
    if ($code -is [System.Array]) { $code = $code[-1] }
    exit $code
}
