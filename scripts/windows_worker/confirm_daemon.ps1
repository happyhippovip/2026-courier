# Decide whether this bootstrap's daemon actually started.
# Older lines in daemon.log do not count. Silence is not a start.

function Wait-CourierDaemon {
    param(
        [Parameter(Mandatory = $true)][string]$LogFile,
        [int64]$LogStart = 0,
        $Process = $null,
        [int]$TimeoutSeconds = 20
    )

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        if ($Process -and $Process.HasExited) { return $false }
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
