# WALL-P0-PLAN-RESUME-OPEN-HALF — report MUSE-MAC-21

TASK_ID=WALL-P0-PLAN-RESUME-OPEN-HALF
STATUS=DONE
WORKER=MUSE-MAC-21 · HOST=MAC · MODE=READ_ONLY · 2026-09-26T14:50Z
WRITER_TIP=a7b92bca (origin/google/mac-longrun-singlewriter, via git show only;
  no checkout, no fetch, no writes)

## Answer: NO
`verify_task_result` does NOT sync plan steps. Only the result-submit path
and the reclaim path do.

## Evidence (a7b92bca:server/app.py line numbers)
- :455 `def verify_task_result():` … :490-496: on PASS sets
  `task["status"]="RECONCILED"` + `goal["current_step_index"]+=1`
  (+ goal DONE when plan exhausted); on FAIL sets
  `task["status"]="FAILED_VERIFICATION"` + goal BLOCKED.
  Zero writes to `goal["workflow_plan"][]` anywhere in :455-498.
- :383-388 `# Sync status back to workflow plan` (step status/worker_id/
  attempts) lives in the RESULT-SUBMIT path ending :397
  `ACK_RESULT_RECEIVED` — not in verify.
- :405 `def reclaim_stale():` syncs step AND task to HUMAN_REQUIRED plus
  worker pointer clearing — the reclaim path the question contrasts with.
- :356 guard references RECONCILED/FAILED_TERMINAL/RESULT_RECEIVED task
  statuses, confirming tasks advance through these states while their plan
  steps do not follow.

## Consequence (open half, as the task name states)
After a verify verdict, `task.status` = RECONCILED / FAILED_VERIFICATION
while the corresponding `workflow_plan` step still shows its pre-verify
status (RESULT_RECEIVED). Any reader of plan steps (vs tasks) sees stale
state: goal `current_step_index` advances but the step row never records
the verdict. Resume-from-step logic (:516 whitelist) still works because it
reads step status — which is exactly why the staleness matters: a
RECONCILED task's step looks resumable-adjacent (RESULT_RECEIVED is not in
the whitelist, so gate holds 400 — no live bug claimed, static fact only).

## Fix shape (minimal, for writer lane — no code touched)
Mirror the :383-388 sync block into verify_task_result after the verdict
branch: set the matching step's status to task status (+ attempts), i.e.
step=RECONCILED on PASS, step=FAILED_VERIFICATION on FAIL. P3/server scope;
owner decision required (writer LOCK MAC-01 live).

BLOCKER=NONE (question answered with file:line evidence)
NEXT=WALL-P0-CANARY-PREFLIGHT (remaining P0)
