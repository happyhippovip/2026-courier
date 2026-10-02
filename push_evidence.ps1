git fetch origin
$branchName = "evidence/google-windows-20260926"
$wtPath = "C:\Users\lol\2026-workspace\evidence-worktree"

# Try to add worktree, if fails create branch
git worktree add $wtPath $branchName
if ($LASTEXITCODE -ne 0) {
    git worktree add -b $branchName $wtPath
}

$destPath = "$wtPath\ops\evidence\google\windows\2026-09-26"
New-Item -ItemType Directory -Force -Path $destPath

Copy-Item -Path "C:\Users\lol\courier_work\google_queue_50\*" -Destination $destPath -Force -Recurse

Set-Location $wtPath
git add ops/evidence/google/windows/2026-09-26/
git commit -m "chore: add windows evidence reports"
git push -u origin $branchName
