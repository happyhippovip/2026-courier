$content = Get-Content -Path "C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\scratch\proof_defect_repair.py" -Raw

$content = $content -replace '\\"expected_evidence\\": \\"success\\"\}', '\"expected_evidence\": \"success\", \"artifact_reference\": \"none\", \"allowed_scope\": \"C:\\\\Users\\\\lol\\\\2026-workspace\"}'
$content = $content -replace 'g = GoalReconciler\(cp, coord_mac_handoff_dir=handoffs_dir\)', 'g = GoalReconciler(cp, handoffs_dir=handoffs_dir)'

Set-Content -Path "C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\scratch\proof_defect_repair.py" -Value $content
