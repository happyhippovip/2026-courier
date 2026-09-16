$content = Get-Content -Path "C:\Users\lol\2026-workspace\courier\chief\goal_reconciler.py" -Raw
$content = $content -replace 'from \.schema import Lane, Host', 'from .types import Lane, Host'
$content = $content -replace 'from \.schema import TaskStatus, TwoLevelDone, Lane', 'from .types import TaskStatus, TwoLevelDone, Lane'
Set-Content -Path "C:\Users\lol\2026-workspace\courier\chief\goal_reconciler.py" -Value $content
