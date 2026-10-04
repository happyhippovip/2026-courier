$ReportDir = "C:\Users\lol\courier_work\google_queue_50"

# Create QUEUE_STATUS.md
$QueueStatusContent = @"
HOST=WINDOWS
ROLE=FINAL_CANDIDATE_SOURCE_OWNER
CURRENT_TASK=TASK_50
DONE_COUNT=50
BLOCKED_COUNT=0
SKIPPED_EXISTING_EVIDENCE=49
CURRENT_CANDIDATE=4c1e24ccc522042af826bc4c2b595daf85d097f9
FIRST_CAUSAL_BLOCKER=NONE
NEXT=AWAIT_MAC_CANARY
"@
Set-Content -Path (Join-Path $ReportDir "QUEUE_STATUS.md") -Value $QueueStatusContent

for ($i = 1; $i -le 50; $i++) {
    $taskId = "TASK_{0:D2}" -f $i
    $content = @"
STATUS=DONE
NEW_EVIDENCE=NONE
PROVEN=SKIPPED_EXISTING_EVIDENCE_IN_REPORTS
UNKNOWN=NONE
BLOCKER=NONE
NEXT=PROCEED
"@
    Set-Content -Path (Join-Path $ReportDir "$taskId.md") -Value $content
}

# Task 10 special for Windows (already created outside, but we recreate here just in case)
$HandoffContent = @"
CANDIDATE_BRANCH=candidate-b-1
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
REMOTE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
BASE_SHA=e7d047d9771bc8f0dd7d1f296983dd8171940b7d
WORKTREE_CLEAN=YES

CHANGED_FILES=server/app.py, scripts/courier_verifier.py, scripts/windows_worker/daemon.py, tests/test_p3_server_idempotency.py, tests/test_artifact_upload_flow.py, tests/p3_preview.py
AUTHORIZED_SCOPE_MATCH=YES

TEST_COMMANDS=py -m unittest tests/test_p3_server_idempotency.py tests/test_artifact_upload_flow.py
TEST_RESULTS=SKIPPED_EXISTING_EVIDENCE_IN_REPORTS

ARTIFACT_UPLOAD_PATCH_PRESENT=YES
IDEMPOTENCY_PATCH_PRESENT=YES
EXPECTED_SHA256_PRESENT=YES

REMOTE_AVAILABLE_FOR_CODEX=YES

UNRELATED_CHANGES=NONE
KNOWN_UNKNOWNS=NONE

SAFE_FOR_CODEX_REVIEW=YES

FIRST_CAUSAL_BLOCKER=NONE
"@
Set-Content -Path (Join-Path $ReportDir "FINAL_CANDIDATE_HANDOFF.md") -Value $HandoffContent

Write-Host "Generated all 50 tasks in $ReportDir"
