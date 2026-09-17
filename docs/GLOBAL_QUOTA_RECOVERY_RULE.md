# GLOBAL PERMANENT RULE — NEVER LOSE QUEUE ON QUOTA / ACCOUNT SWITCH

## OBJECTIVE
A provider/account quota interruption must NEVER cause queued work to disappear, restart, reorder, or depend on scrolling chat history.

Before ANY provider/account/session stop:
**persist canonical recovery state.**

## REQUIRED PERSISTED FIELDS
- batch_id, prompt_id, sequence, status, depends_on
- goal_id, task_id, attempt_id, dispatch_id, execution_ref
- branch, head_sha, dirty_worktree, changed_files, artifact_refs
- last_completed_prompt_id, active_prompt_id, next_prompt_id
- last_completed_step, next_action, blocker
- provider, provider_status, provider_failure_reason, account_session_ref
- completion_evidence_refs

## QUOTA / LIMIT CLASSIFICATION
If an error indicates:
- individual quota reached
- provider quota reached
- rate limit requiring account/provider switch
- account unavailable
- temporary provider access loss

then active work becomes: **WAITING_PROVIDER**

NOT: `FAILED_TERMINAL`, `DONE`, `COMPLETED`, `CANCELLED`

## RULES
1. NEVER delete queued items.
2. NEVER decrement/consume remaining queue because a prompt was merely displayed in UI.
3. NEVER treat "prompt accepted" as completed.
4. NEVER treat chat delivery as execution.
5. COMPLETED requires durable evidence.
6. Keep all not-yet-completed items QUEUED.
7. Preserve dirty edits.
8. Preserve exact branch/head.
9. Pure provider/account wait does NOT increment attempt_id.
10. Pure provider/account wait does NOT create a new logical task.
11. Close unnecessary temporary task-owned processes before waiting.
12. Preserve ambiguous external-effect state fail-closed.

## ACCOUNT SWITCH RECOVERY
When a new provider/account/agent starts:
1. Read canonical Courier durable state FIRST.
2. Inspect git status/diff/head.
3. Do NOT use chat scrollback as source of truth.
4. Do NOT ask operator to paste old prompts again.
5. Skip every item with valid COMPLETED evidence.
6. Resume lowest-sequence `IN_PROGRESS` or `WAITING_PROVIDER` item first.
7. Then continue dependency-satisfied `QUEUED` items automatically.
8. Continue until queue empty or genuine wall.

**UI IS NEVER AUTHORITY.**
Docs are not runtime task truth. Courier server/state remains authoritative.
