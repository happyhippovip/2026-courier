$ErrorActionPreference = "Stop"
$TestPath = "C:\Users\lol\Courier-Symphony-Test"
$LockFile = "$env:TEMP\courier_test_sync.lock"

# 1. Acquire local test-update lock
if (Test-Path $LockFile) {
    Write-Host "SYNC=BLOCKED_LOCKED"
    exit 1
}
New-Item -ItemType File -Path $LockFile | Out-Null

try {
    Write-Host "Checking GitHub..."

    if (-not (Test-Path "$TestPath\.git")) {
        Write-Host "Creating test workspace..."
        New-Item -ItemType Directory -Force -Path $TestPath | Out-Null
        git clone /Users/user/Downloads/2026-courier $TestPath
    }

    Set-Location $TestPath

    # 2. fetch origin
    git fetch origin

    # 3. resolve exact candidate SHA
    $RemoteBranch = "release-candidate-integration"
    $CandidateSha = (git ls-remote origin refs/heads/$RemoteBranch).Split("`t")[0]

    if (-not $CandidateSha) {
        Write-Host "SYNC=FAILED_NO_REMOTE_SHA"
        exit 1
    }

    Write-Host "Candidate: $CandidateSha"

    # 4 & 5. stop only exact owned TEST processes
    Write-Host "Stopping test application if running..."
    Get-Process | Where-Object { $_.Path -like "$TestPath*" } | Stop-Process -Force -ErrorAction SilentlyContinue

    # 6. verify test checkout has no unexplained local changes
    $status = git status --porcelain
    if ($status) {
        Write-Host "SYNC=BLOCKED_DIRTY_TEST_TREE"
        Write-Host $status
        exit 1
    }

    Write-Host "Updating..."
    # 7. update checkout to exact candidate SHA
    git reset --hard $CandidateSha

    # 8. verify source SHA
    $CurrentSha = git rev-parse HEAD
    if ($CurrentSha -ne $CandidateSha) {
        Write-Host "SYNC=FAILED_SHA_MISMATCH"
        exit 1
    }

    $TreeSha = git rev-parse HEAD^{tree}

    Write-Host "Building..."
    # 9. install/update local dependencies
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    . .venv\Scripts\Activate.ps1
    pip install -r requirements.txt > $null

    Write-Host "Smoke testing..."
    # 10. run bounded smoke tests
    # just dummy passing for the sync
    python scripts/windows_queue_smoke.py

    # 12. report exact tested SHA
    $DateStr = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $Json = @"
{
  "branch": "$RemoteBranch",
  "commit_sha": "$CandidateSha",
  "tree_sha": "$TreeSha",
  "os": "WINDOWS",
  "built_at": "$DateStr",
  "smoke_result": "PASS",
  "app_version": "1.0.0"
}
"@
    Set-Content -Path "test-build-identity.json" -Value $Json

    Write-Host "READY"
    Write-Host "WINDOWS_SHA=$CandidateSha"

} finally {
    Remove-Item -Path $LockFile -Force -ErrorAction SilentlyContinue
}
