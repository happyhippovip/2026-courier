# Decide whether this bootstrap's daemon actually started.
# Older lines in daemon.log do not count. Silence is not a start.

function Test-CourierLocalController {
    param(
        [string]$Token,
        [int]$Port
    )
    # Courier.exe is the launcher. It serves the controller on loopback.
    # A remote COURIER_SERVER being up does not mean this PC started.
    if ([string]::IsNullOrWhiteSpace($Token) -or $Port -lt 1) { return $false }
    $res = $null
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/v1/health")
        $req.Timeout = 1000
        $req.Headers.Add("X-Courier-Token", $Token)
        $res = $req.GetResponse()
        return [int]$res.StatusCode -eq 200
    } catch {
        return $false
    } finally {
        if ($res) { $res.Close() }
    }
}

function Wait-CourierDaemon {
    param(
        [Parameter(Mandatory = $true)][string]$LogFile,
        [int64]$LogStart = 0,
        $Process = $null,
        [int]$TimeoutSeconds = 20,
        [string]$Token = "",
        [int]$ControllerPort = 0
    )

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        if ($Process -and $Process.HasExited) { return $false }
        if (Test-CourierLocalController -Token $Token -Port $ControllerPort) { return $true }
        $text = ""
        if (Test-Path -LiteralPath $LogFile) {
            $stream = $null
            try {
                $stream = [System.IO.File]::Open($LogFile, 'Open', 'Read', 'ReadWrite')
                if ($stream.Length -gt $LogStart) {
                    $stream.Position = $LogStart
                    $reader = New-Object System.IO.StreamReader($stream)
                    $text = $reader.ReadToEnd()
                    $reader.Dispose()
                    $stream = $null
                }
            } catch {
                $text = ""
            } finally {
                if ($stream) { $stream.Dispose() }
            }
        }
        if ($text -match "FATAL:") { return $false }
        if ($text -match "Windows Worker HTTP Daemon started") { return $true }
        if ($watch.Elapsed.TotalSeconds -ge $TimeoutSeconds) { return $false }
        Start-Sleep -Seconds 1
    }
}
