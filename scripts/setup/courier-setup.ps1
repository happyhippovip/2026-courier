# Courier host setup for Windows.
#
# One line in PowerShell (normal user, no admin):
#   irm https://raw.githubusercontent.com/happyhippovip/2026-courier/lane/L6-host-setup/scripts/setup/courier-setup.ps1 | iex
# Flags, when piping: set COURIER_SETUP_ARGS first, for example
#   $env:COURIER_SETUP_ARGS='--check'; irm <url> | iex
# or run a saved copy: powershell -File courier-setup.ps1 -Check
#   -Check / --check            doctor only, writes nothing
#   -WithGodot / --with-godot   also install Godot 4 (winget, user scope)
#   -Uninstall / --uninstall    remove this user's CourierWindowsWorker task
#
# Safe to run again. It never elevates, never stops a process, never deletes,
# stashes, resets or cleans anything, and never reads credentials. A checkout
# with local changes or another branch is left alone; a fresh sibling clone is
# used instead. Unknown state fails closed with a message.
#
# Result codes: 0 HOST READY, 2 HOST PARTIAL, 3 HOST BLOCKED, 64 usage error.
# Under "irm | iex" the code lands in $LASTEXITCODE and the window stays open;
# the script never calls exit there. Nothing depends on $PSScriptRoot.

param(
    [switch]$Check,
    [switch]$WithGodot,
    [switch]$Uninstall
)

function Invoke-CourierSetup {
    param(
        [bool]$CheckMode,
        [bool]$GodotMode,
        [bool]$UninstallMode
    )

    # Local to this function, so an "iex" session keeps its own preference.
    $ErrorActionPreference = 'Continue'
    $ProgressPreference = 'SilentlyContinue'

    $Version = '1'
    $RepoUrl = if ($env:COURIER_REPO_URL) { $env:COURIER_REPO_URL } else { 'https://github.com/happyhippovip/2026-courier.git' }
    $Branch = if ($env:COURIER_BRANCH) { $env:COURIER_BRANCH } else { 'integration/v1' }
    $TaskName = 'CourierWindowsWorker'
    $MaxHeavyBuilders = 1
    $MinSwapFreeMb = 1024
    $MinFreeRamMb = 2048
    $MinDiskFreeMb = 10240

    $state = @{
        Status = 'READY'; Notes = @(); Actions = @(); Next = @()
    }
    function Add-Note([string]$t) { $state.Notes += "- $t" }
    function Add-Action([string]$t) { $state.Actions += "- $t" }
    function Add-Next([string]$t) { $state.Next += "- $t" }
    function Set-Partial { if ($state.Status -eq 'READY') { $state.Status = 'PARTIAL' } }
    function Set-Blocked { $state.Status = 'BLOCKED' }
    function Say([string]$t) { Write-Host $t }

    $Mode = 'setup'
    if ($CheckMode -and $UninstallMode) { Say 'Choose one of --check or --uninstall.'; return 64 }
    if ($CheckMode) { $Mode = 'check' }
    if ($UninstallMode) { $Mode = 'uninstall' }

    $onWindows = ($env:OS -eq 'Windows_NT')
    if ($env:COURIER_SETUP_OS) { $onWindows = ($env:COURIER_SETUP_OS -eq 'Windows_NT') }
    if (-not $onWindows) {
        Say "HOST BLOCKED: this script is for Windows. Nothing was changed."
        Say "macOS: use scripts/setup/courier-setup.sh."
        return 3
    }
    $isAdmin = $false
    try {
        $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { $isAdmin = $false }
    if ($isAdmin) {
        Say 'HOST BLOCKED: this window runs as Administrator. Open a normal PowerShell window and run the line again. Nothing was changed.'
        return 3
    }
    $UserHome = $env:USERPROFILE
    if ([string]::IsNullOrWhiteSpace($UserHome) -or -not (Test-Path -LiteralPath $UserHome -PathType Container)) {
        Say 'HOST BLOCKED: USERPROFILE is not a folder. Nothing was changed.'
        return 3
    }
    $Base = Join-Path $UserHome 'Courier'
    if (Test-Path -LiteralPath $Base) {
        $baseItem = Get-Item -LiteralPath $Base -Force
        if (-not $baseItem.PSIsContainer -or ($baseItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Say 'HOST BLOCKED: ~\Courier is a link or not a folder. Nothing was changed.'
            return 3
        }
    }

    function Get-Tilde([string]$p) {
        if ([string]::IsNullOrEmpty($p)) { return 'none' }
        if ($p.StartsWith($UserHome, [StringComparison]::OrdinalIgnoreCase)) { return '~' + $p.Substring($UserHome.Length) }
        return $p
    }
    function Get-Sha12([string]$t) {
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($t))
            return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0, 12)
        } finally { $sha.Dispose() }
    }
    function Get-OneLine($value) {
        if ($null -eq $value) { return '' }
        $line = (@($value) | Select-Object -First 1) -as [string]
        if ($null -eq $line) { return '' }
        $line = ($line -replace '[^\x20-\x7E]', '').Trim()
        if ($line.Length -gt 60) { $line = $line.Substring(0, 60) }
        return $line
    }
    function Get-First($value) {
        # First line, untruncated: for git values such as URLs and hashes.
        $line = (@($value) | Select-Object -First 1) -as [string]
        if ($null -eq $line) { return '' }
        return $line.Trim()
    }
    function Test-Cmd([string]$name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
    function Invoke-Quiet {
        param([string]$Exe, [string[]]$Arguments)
        $out = & $Exe @Arguments 2>$null
        return [pscustomobject]@{ Code = $LASTEXITCODE; Out = $out }
    }
    function Update-PathFromEnvironment {
        # Read-only refresh so tools installed a moment ago resolve here.
        $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $user = [Environment]::GetEnvironmentVariable('Path', 'User')
        $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
    }

    $HostName = $env:COMPUTERNAME
    $HostHash = 'h-' + (Get-Sha12 ('courier-host-v1:' + $HostName))

    function Protect-Report([string]$text) {
        $pairs = @(
            @($UserHome, '~'),
            @($env:COMPUTERNAME, '<host>'),
            @($env:USERDOMAIN, '<domain>'),
            @($env:USERNAME, '<user>')
        )
        foreach ($p in $pairs) {
            if (-not [string]::IsNullOrEmpty($p[0]) -and $p[0].Length -ge 2) {
                $text = $text -replace [regex]::Escape($p[0]), $p[1]
            }
        }
        $text = $text -replace '(?i)[A-Z]:\\Users\\[^\\\s]+', 'C:\Users\<user>'
        $text = $text -replace 'gh[pousr]_[A-Za-z0-9]+', '<token>'
        $text = $text -replace 'github_pat_[A-Za-z0-9_]+', '<token>'
        $text = $text -replace 'sk-[A-Za-z0-9_-]{16,}', '<token>'
        $text = $text -replace '(?i)bearer [A-Za-z0-9._~+/=-]+', 'Bearer <token>'
        $text = $text -replace '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '<email>'
        return $text
    }

    Say "Courier host setup ($Mode) ..."

    # ---- doctor -----------------------------------------------------------
    $d = [ordered]@{
        Os = 'unknown'; Cpu = 'unknown'; Cores = 'unknown'; RamMb = 'unknown'; FreeRamMb = 'unknown'
        PageTotalMb = 'unknown'; PageFreeMb = 'unknown'; DiskFreeMb = 'unknown'
        Git = 'missing'; Python = 'missing'; PythonExe = ''; Gh = 'no'; GhAuth = 'no'
        Muse = 'missing'; Agy = 'no'; Godot = 'no'; Winget = 'no'; Procs = 'unknown'
        Dirty = 0; DirtySkipped = 0
    }
    function Get-Doctor {
        try {
            $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
            $d.Os = Get-OneLine ("$($os.Caption) $($os.Version)")
            $d.RamMb = [int]([double]$os.TotalVisibleMemorySize / 1024)
            $d.FreeRamMb = [int]([double]$os.FreePhysicalMemory / 1024)
        } catch { }
        try {
            $cpus = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
            $d.Cpu = Get-OneLine $cpus[0].Name
            $d.Cores = ($cpus | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
        } catch { }
        try {
            $pf = @(Get-CimInstance Win32_PageFileUsage -ErrorAction Stop)
            if ($pf.Count -gt 0) {
                $alloc = ($pf | Measure-Object -Property AllocatedBaseSize -Sum).Sum
                $used = ($pf | Measure-Object -Property CurrentUsage -Sum).Sum
                $d.PageTotalMb = [int]$alloc
                $d.PageFreeMb = [int]($alloc - $used)
            } else {
                $d.PageTotalMb = 0; $d.PageFreeMb = 0
            }
        } catch { }
        try {
            $drive = (Split-Path -Path $UserHome -Qualifier -ErrorAction Stop).TrimEnd(':')
            $d.DiskFreeMb = [int]((Get-PSDrive -Name $drive -ErrorAction Stop).Free / 1MB)
        } catch { }
        Get-Tools
        try {
            $me = $PID
            $procs = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                $_.ProcessId -ne $me -and (
                    $_.Name -eq 'Courier.exe' -or
                    ($_.CommandLine -and $_.CommandLine -match 'windows_worker\\daemon\.py|courier_worker|muse_wall|run_autonomous_loop') ) -and
                    -not ($_.CommandLine -and $_.CommandLine -match 'courier-setup')
            })
            $d.Procs = $procs.Count
        } catch { }
    }
    function Get-Tools {
        $d.Git = 'missing'
        if (Test-Cmd git) {
            $r = Invoke-Quiet git @('--version')
            if ($r.Code -eq 0) { $d.Git = 'yes ' + ((Get-OneLine $r.Out) -replace '^git version ', '') }
        }
        $d.Python = 'missing'; $d.PythonExe = ''
        if (Test-Cmd py) {
            $r = Invoke-Quiet py @('-3.12', '-c', 'import sys; print(sys.executable)')
            if ($r.Code -eq 0 -and (Get-OneLine $r.Out)) {
                $d.PythonExe = (@($r.Out) | Select-Object -First 1)
                $d.Python = '3.12'
            }
        }
        if (-not $d.PythonExe) {
            foreach ($c in @('python3.12', 'python')) {
                $cmd = Get-Command $c -ErrorAction SilentlyContinue | Select-Object -First 1
                if (-not $cmd) { continue }
                # The WindowsApps python.exe is a Store stub, not an interpreter.
                if ($cmd.Source -match '\\WindowsApps\\') { continue }
                $r = Invoke-Quiet $cmd.Source @('--version')
                $v = Get-OneLine $r.Out
                if ($v -match '^Python 3\.12') { $d.PythonExe = $cmd.Source; $d.Python = $v -replace '^Python ', ''; break }
            }
        }
        $d.Gh = 'no'; $d.GhAuth = 'no'
        if (Test-Cmd gh) {
            $d.Gh = 'yes'
            # Exit status only; the output may name the account and is discarded.
            & gh auth status *> $null
            if ($LASTEXITCODE -eq 0) { $d.GhAuth = 'yes' }
        }
        $d.Muse = 'missing'
        if (Test-Cmd muse) {
            $r = Invoke-Quiet muse @('--version')
            $v = Get-OneLine $r.Out
            $d.Muse = if ($v) { $v } else { 'present (version unknown)' }
        }
        $d.Agy = if (Test-Cmd agy) { 'yes' } else { 'no' }
        $d.Godot = 'no'
        if ((Test-Cmd godot) -or (Get-Command 'Godot*' -CommandType Application -ErrorAction SilentlyContinue)) { $d.Godot = 'yes' }
        elseif ($env:LOCALAPPDATA -and (Test-Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\GodotEngine.GodotEngine*'))) { $d.Godot = 'yes' }
        $d.Winget = if (Test-Cmd winget) { 'yes' } else { 'no' }
    }
    function Test-ProtectedPath([string]$p) {
        foreach ($name in @('Desktop', 'Documents', 'Downloads', 'OneDrive')) {
            $root = Join-Path $UserHome $name
            if ($p -and $p.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { return $true }
        }
        return $false
    }
    function Get-DirtyCount {
        $d.Dirty = 0; $d.DirtySkipped = 0
        if (-not $d.Git.StartsWith('yes')) { $d.Dirty = 'unknown'; return }
        if (-not (Test-Path -LiteralPath $Base)) { return }
        foreach ($dir in @(Get-ChildItem -LiteralPath $Base -Directory -Force -ErrorAction SilentlyContinue)) {
            if (-not (Test-Path -LiteralPath (Join-Path $dir.FullName '.git'))) { continue }
            $r = Invoke-Quiet git @('-C', $dir.FullName, 'worktree', 'list', '--porcelain')
            foreach ($line in @($r.Out)) {
                if (-not ($line -match '^worktree (.+)$')) { continue }
                $wt = $Matches[1] -replace '/', '\'
                if (Test-ProtectedPath $wt) { $d.DirtySkipped++; continue }
                if (-not (Test-Path -LiteralPath $wt)) { continue }
                $s = Invoke-Quiet git @('-C', $wt, 'status', '--porcelain')
                if ($s.Code -eq 0 -and @($s.Out | Where-Object { $_ }).Count -gt 0) { $d.Dirty++ }
            }
        }
    }

    # ---- prerequisites (user scope only) ------------------------------------
    function Install-WingetUser([string]$id) {
        $r = Invoke-Quiet winget @('install', '--id', $id, '--exact', '--scope', 'user', '--silent', '--accept-package-agreements', '--accept-source-agreements')
        return ($r.Code -eq 0)
    }
    function Install-Prereqs {
        if ($Mode -eq 'check') { return }
        if ($d.Winget -ne 'yes') {
            Add-Note 'winget missing; prerequisites were not installed (App Installer from the Microsoft Store provides it)'
            return
        }
        $changed = $false
        if ($d.Git -eq 'missing') {
            if (Install-WingetUser 'Git.Git') { Add-Action 'installed Git (winget, user scope)'; $changed = $true } else { Add-Note 'Git: no user-scope install succeeded' }
        }
        if (-not $d.PythonExe) {
            if (Install-WingetUser 'Python.Python.3.12') { Add-Action 'installed Python 3.12 (winget, user scope)'; $changed = $true } else { Add-Note 'Python 3.12: user-scope install failed' }
        }
        if ($d.Gh -eq 'no') {
            if (Install-WingetUser 'GitHub.cli') { Add-Action 'installed GitHub CLI (winget, user scope)'; $changed = $true } else { Add-Note 'GitHub CLI: no user-scope package; skipped' }
        }
        if ($GodotMode -and $d.Godot -eq 'no') {
            if (Install-WingetUser 'GodotEngine.GodotEngine') { Add-Action 'installed Godot 4 (winget, user scope)'; $changed = $true } else { Add-Note 'Godot: user-scope install failed'; Set-Partial }
        }
        if ($changed) { Update-PathFromEnvironment; Get-Tools }
    }

    # ---- repository ---------------------------------------------------------
    function Get-RepoState([string]$dir) {
        if (-not (Test-Path -LiteralPath $dir)) { return 'ABSENT' }
        $item = Get-Item -LiteralPath $dir -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { return 'SYMLINK' }
        if (-not (Test-Path -LiteralPath (Join-Path $dir '.git') -PathType Container)) { return 'NOT_GIT' }
        $url = Get-First (Invoke-Quiet git @('-C', $dir, 'config', '--get', 'remote.origin.url')).Out
        $okRemote = ($url -eq $RepoUrl) -or ($url -match 'github\.com[/:]happyhippovip/2026-courier(\.git)?$')
        if (-not $okRemote) { return 'FOREIGN_REMOTE' }
        $br = Get-First (Invoke-Quiet git @('-C', $dir, 'symbolic-ref', '--quiet', '--short', 'HEAD')).Out
        if ($br -ne $Branch) { return 'FOREIGN_BRANCH' }
        $s = Invoke-Quiet git @('-C', $dir, 'status', '--porcelain')
        if ($s.Code -ne 0) { return 'UNREADABLE' }
        if (@($s.Out | Where-Object { $_ }).Count -gt 0) { return 'DIRTY' }
        return 'OK'
    }
    $repo = @{ Dir = ''; State = 'NONE' }
    function Invoke-Clone([string]$dir) {
        $env:GIT_TERMINAL_PROMPT = '0'
        $r = Invoke-Quiet git @('clone', '--quiet', '--branch', $Branch, '--single-branch', $RepoUrl, $dir)
        if ($r.Code -eq 0) {
            Add-Action "cloned $Branch into $(Get-Tilde $dir)"
            $repo.Dir = $dir; $repo.State = 'CLONED'
            return $true
        }
        Add-Note "clone into $(Get-Tilde $dir) failed (network or access)"
        return $false
    }
    function Update-Repo([string]$dir) {
        $env:GIT_TERMINAL_PROMPT = '0'
        $f = Invoke-Quiet git @('-C', $dir, 'fetch', '--quiet', 'origin', $Branch)
        if ($f.Code -ne 0) {
            Add-Note "$(Get-Tilde $dir): fetch failed; using the checkout as it is"
            $repo.Dir = $dir; $repo.State = 'STALE'
            return $true
        }
        $head = Get-First (Invoke-Quiet git @('-C', $dir, 'rev-parse', 'HEAD')).Out
        $fetched = Get-First (Invoke-Quiet git @('-C', $dir, 'rev-parse', 'FETCH_HEAD')).Out
        if ($head -and $head -eq $fetched) { $repo.Dir = $dir; $repo.State = 'UP_TO_DATE'; return $true }
        $anc = Invoke-Quiet git @('-C', $dir, 'merge-base', '--is-ancestor', 'HEAD', 'FETCH_HEAD')
        if ($anc.Code -ne 0) { Add-Note "$(Get-Tilde $dir): has local commits; left untouched"; return $false }
        $m = Invoke-Quiet git @('-C', $dir, 'merge', '--ff-only', '--quiet', 'FETCH_HEAD')
        if ($m.Code -eq 0) {
            Add-Action "fast-forwarded $(Get-Tilde $dir)"
            $repo.Dir = $dir; $repo.State = 'UPDATED'
            return $true
        }
        Add-Note "$(Get-Tilde $dir): fast-forward failed; left untouched"
        return $false
    }
    function Invoke-RepoStep {
        foreach ($cand in @((Join-Path $Base '2026-courier'), (Join-Path $Base '2026-courier-host'))) {
            $st = Get-RepoState $cand
            if ($st -eq 'OK') {
                if ($Mode -eq 'check') { $repo.Dir = $cand; $repo.State = 'OK (update not attempted in --check)'; return }
                if (Update-Repo $cand) { return }
            } elseif ($st -eq 'ABSENT') {
                if ($Mode -eq 'check') { $repo.State = "WOULD_CLONE into $(Get-Tilde $cand)"; return }
                if (-not (Invoke-Clone $cand)) { Set-Blocked }
                return
            } else {
                Add-Note "$(Get-Tilde $cand): $st; left untouched"
            }
        }
        $cand = Join-Path $Base ('2026-courier-host-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
        if ($Mode -eq 'check') { $repo.State = 'WOULD_CLONE into a fresh sibling'; return }
        if (-not (Invoke-Clone $cand)) { Set-Blocked }
    }

    # ---- admission and host config -------------------------------------------
    $adm = @{ State = 'OPEN'; Why = @() }
    function Get-Admission {
        if (-not ($d.FreeRamMb -is [int]) -or -not ($d.PageFreeMb -is [int])) {
            $adm.State = 'PARKED'; $adm.Why = @('metrics unreadable (fails closed)'); return
        }
        if ($d.FreeRamMb -lt $MinFreeRamMb) { $adm.State = 'PARKED'; $adm.Why += "free RAM $($d.FreeRamMb) MB < $MinFreeRamMb MB" }
        if ($d.PageTotalMb -is [int] -and $d.PageTotalMb -gt 0 -and $d.PageFreeMb -lt $MinSwapFreeMb) {
            $adm.State = 'PARKED'; $adm.Why += "pagefile free $($d.PageFreeMb) MB < $MinSwapFreeMb MB"
        }
        if ($d.DiskFreeMb -is [int] -and $d.DiskFreeMb -lt $MinDiskFreeMb) { $adm.State = 'PARKED'; $adm.Why += "disk free $($d.DiskFreeMb) MB < $MinDiskFreeMb MB" }
    }
    function Write-Owned([string]$dest, [string]$content, [string]$marker) {
        if (Test-Path -LiteralPath $dest) {
            $existing = [IO.File]::ReadAllText($dest)
            if (-not $existing.Contains($marker)) {
                Add-Note "$(Get-Tilde $dest) exists and was not written by courier-setup; left untouched"
                Set-Partial
                return $false
            }
        }
        $tmp = "$dest.tmp.$PID"
        try {
            [IO.File]::WriteAllText($tmp, $content, (New-Object Text.UTF8Encoding($false)))
            if (Test-Path -LiteralPath $dest) { [IO.File]::Replace($tmp, $dest, [NullString]::Value) } else { [IO.File]::Move($tmp, $dest) }
            return $true
        } catch {
            Add-Note "could not write $(Get-Tilde $dest)"
            Set-Partial
            return $false
        }
    }
    $hostConfig = 'not written'
    function Write-HostConfig {
        $cfgPath = Join-Path $Base 'host-config.json'
        if ($Mode -eq 'check') {
            if (Test-Path -LiteralPath $cfgPath) { return 'present' }
            return 'WOULD_WRITE'
        }
        $cfg = [ordered]@{
            schema = 'courier.host_config.v1'
            written_by = 'courier-setup'
            setup_version = $Version
            updated_at = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
            host_id = $HostHash
            os = 'windows'
            ram_total_mb = "$($d.RamMb)"
            repo_path = (Get-Tilde $repo.Dir)
            repo_branch = $Branch
            start_heavy_workers_on_setup = $false
            resource_admission = [ordered]@{
                max_heavy_builders = $MaxHeavyBuilders
                park_new_work_when = [ordered]@{
                    free_ram_mb_below = $MinFreeRamMb
                    swap_free_mb_below = $MinSwapFreeMb
                    disk_free_mb_below = $MinDiskFreeMb
                    metrics_unreadable = $true
                }
                running_work = 'never stopped by admission; only new work is parked'
            }
        }
        $json = $cfg | ConvertTo-Json -Depth 5
        if (Write-Owned $cfgPath $json 'courier.host_config.v1') {
            Add-Action 'wrote ~\Courier\host-config.json'
            return "written (max heavy builders $MaxHeavyBuilders)"
        }
        return 'not written'
    }

    # ---- service ------------------------------------------------------------
    function Test-SameUser([string]$principal) {
        if ([string]::IsNullOrWhiteSpace($principal)) { return $false }
        $tail = ($principal -split '\\')[-1]
        return $tail.Equals($env:USERNAME, [StringComparison]::OrdinalIgnoreCase)
    }
    function Invoke-ServiceStep {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task) {
            if (Test-SameUser $task.Principal.UserId) { return 'REGISTERED (already present for this user; left as is)' }
            Add-Note "task $TaskName runs as another account (for example SYSTEM); replacing it needs admin, so it is left untouched"
            Set-Partial
            return 'FOREIGN_PRINCIPAL (left untouched)'
        }
        if (-not $repo.Dir) { Set-Partial; if ($Mode -eq 'check') { return 'NOT_REGISTERED' } else { return 'SKIPPED (no checkout)' } }
        $workerDir = Join-Path $repo.Dir 'scripts\windows_worker'
        $installer = Join-Path $workerDir 'install_service.ps1'
        if (-not (Test-Path -LiteralPath $installer)) { Set-Partial; return 'SKIPPED (installer missing in checkout)' }
        $text = [IO.File]::ReadAllText($installer)
        $userContract = $text.Contains('RunLevel Limited') -and $text.Contains('InstallDir') -and -not $text.Contains('"SYSTEM"')
        if (-not $userContract) {
            # Older installers register a SYSTEM boot task and need admin.
            Set-Partial
            return "SKIPPED (installer in this checkout needs admin; waiting for the user-level install_service.ps1 on $Branch)"
        }
        if ($Mode -eq 'check') { Set-Partial; return 'NOT_REGISTERED (setup would register the logon task without starting it)' }
        # A child process runs the saved installer; -ExecutionPolicy applies to
        # that process only and changes no machine or user policy.
        $hostExe = (Get-Process -Id $PID).Path
        & $hostExe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer -InstallDir $workerDir *> $null
        if ($LASTEXITCODE -eq 0) {
            Add-Action "registered logon task $TaskName via install_service.ps1 (not started)"
            return 'REGISTERED (logon task for this user; not started now)'
        }
        Set-Partial
        return 'FAILED (installer exit non-zero)'
    }
    function Invoke-Uninstall {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if (-not $task) { return 'NOT_INSTALLED (nothing to remove)' }
        if (-not (Test-SameUser $task.Principal.UserId)) {
            Set-Blocked
            Add-Next 'the task belongs to another account; scripts/windows_worker/uninstall.ps1 handles that and needs an admin you start yourself'
            return 'FOREIGN_PRINCIPAL (not removed)'
        }
        if ("$($task.State)" -eq 'Running') {
            Set-Blocked
            Add-Next 'stop the Courier worker through its owner first, then run --uninstall again'
            return 'RUNNING (not removed; setup never stops a worker)'
        }
        # scripts/windows_worker/uninstall.ps1 needs admin and also deletes the
        # program folder; setup does only the user-scope part: the task it made.
        try {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
            Add-Action "removed logon task $TaskName"
            return 'UNINSTALLED (task removed; checkouts, config and data kept)'
        } catch {
            Set-Blocked
            return 'UNINSTALL_FAILED'
        }
    }

    # ---- run ----------------------------------------------------------------
    Get-Doctor
    $service = 'UNKNOWN'
    if ($Mode -eq 'uninstall') {
        $service = Invoke-Uninstall
        $repo.State = 'not inspected'; $hostConfig = 'kept'; $d.Dirty = 'not counted'; $adm.State = 'n/a'
    } else {
        if ($Mode -eq 'setup') {
            try { New-Item -ItemType Directory -Force -Path $Base -ErrorAction Stop | Out-Null } catch {
                Say 'HOST BLOCKED: cannot create ~\Courier. Nothing else was changed.'
                return 3
            }
        }
        Install-Prereqs
        if (-not $d.Git.StartsWith('yes')) {
            $repo.State = 'SKIPPED (git missing)'
            Add-Next 'install Git for Windows (winget install --id Git.Git --scope user), then run this line again'
            Set-Blocked
        } else {
            Invoke-RepoStep
        }
        Get-DirtyCount
        if (-not $d.PythonExe) { Add-Next 'Python 3.12 missing: winget install --id Python.Python.3.12 --scope user'; Set-Partial }
        Get-Admission
        if ($state.Status -eq 'BLOCKED' -and -not $repo.Dir) {
            $hostConfig = 'not written (blocked)'; $service = 'SKIPPED (blocked)'
        } else {
            $hostConfig = Write-HostConfig
            $service = Invoke-ServiceStep
        }
        if ($d.GhAuth -ne 'yes') { Add-Next "GitHub CLI not signed in: run 'gh auth login' yourself (setup never handles credentials)" }
        if ($d.Muse -eq 'missing') { Add-Next 'muse CLI not found in PATH' }
        if ($adm.State -ne 'OPEN') { Add-Next 'new heavy work stays parked until memory/pagefile recover' }
    }

    $sha = 'none'
    if ($repo.Dir -and $d.Git.StartsWith('yes')) { $sha = Get-OneLine (Invoke-Quiet git @('-C', $repo.Dir, 'rev-parse', '--short=12', 'HEAD')).Out }
    $modeLabel = switch ($Mode) { 'check' { 'check (no changes)' } 'uninstall' { 'uninstall' } default { 'setup' } }
    $admLine = $adm.State
    if (@($adm.Why).Count -gt 0) { $admLine += ' (' + ($adm.Why -join '; ') + ')' }
    function Join-Items($items) { if (@($items).Count -eq 0) { return '- none' } return ($items -join "`n") }

    $build = {
        @(
            "COURIER HOST SETUP REPORT v$Version"
            "HOST $($state.Status)"
            "mode: $modeLabel"
            "time_utc: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
            "host_id: $HostHash"
            "os: $($d.Os)"
            "cpu: $($d.Cpu), $($d.Cores) logical cores"
            "ram_mb: total $($d.RamMb), free $($d.FreeRamMb)"
            "pagefile_mb: total $($d.PageTotalMb), free $($d.PageFreeMb)"
            "disk_free_mb: $($d.DiskFreeMb)"
            "git: $($d.Git)"
            "python3.12: $($d.Python)"
            "gh: $($d.Gh), auth: $($d.GhAuth)"
            "muse: $($d.Muse)"
            "agy: $($d.Agy)"
            "godot: $($d.Godot)"
            "winget: $($d.Winget)"
            "courier_processes: $($d.Procs)"
            "dirty_worktrees: $($d.Dirty) (skipped in protected folders: $($d.DirtySkipped))"
            "repo: $(Get-Tilde $repo.Dir) @ $sha [$($repo.State)]"
            "host_config: $hostConfig"
            "service: $service"
            "admission: $admLine, max heavy builders $MaxHeavyBuilders"
            "heavy_workers_started: 0"
            'actions:'
            (Join-Items $state.Actions)
            'notes:'
            (Join-Items $state.Notes)
            'next:'
            (Join-Items $state.Next)
        ) -join "`n"
    }
    $report = Protect-Report (& $build)
    if ($Mode -ne 'check' -and (Test-Path -LiteralPath $Base)) {
        if (Write-Owned (Join-Path $Base 'setup-report.txt') $report 'COURIER HOST SETUP REPORT') {
            Say 'Report: ~\Courier\setup-report.txt'
        }
        $report = Protect-Report (& $build)
    }
    Write-Host $report
    if ($Mode -ne 'check') {
        try { Set-Clipboard -Value $report -ErrorAction Stop; Say 'Report copied to the clipboard. Paste it into the chat.' } catch { }
    }
    Write-Host ''
    Write-Host "==== HOST $($state.Status) ===="
    switch ($state.Status) { 'READY' { return 0 } 'PARTIAL' { return 2 } default { return 3 } }
}

# Flags also arrive through COURIER_SETUP_ARGS, because "irm | iex" cannot pass them.
$courierCheck = [bool]$Check
$courierGodot = [bool]$WithGodot
$courierUninstall = [bool]$Uninstall
$courierUsage = $false
if ($env:COURIER_SETUP_ARGS) {
    foreach ($courierArg in ($env:COURIER_SETUP_ARGS -split '\s+' | Where-Object { $_ })) {
        switch ($courierArg) {
            '--check' { $courierCheck = $true }
            '--with-godot' { $courierGodot = $true }
            '--uninstall' { $courierUninstall = $true }
            default { Write-Host "Unknown option in COURIER_SETUP_ARGS: $courierArg"; $courierUsage = $true }
        }
    }
}
if ($courierUsage) {
    $courierCode = 64
} else {
    $courierCode = Invoke-CourierSetup -CheckMode $courierCheck -GodotMode $courierGodot -UninstallMode $courierUninstall
}
$global:LASTEXITCODE = $courierCode
# Only a saved copy run as a script file may exit; "iex" must keep the window.
if ($MyInvocation.MyCommand.CommandType -eq 'ExternalScript') { exit $courierCode }
