# User Acceptance B — "Braucht dich": "Was wartet auf mich?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
A normal user cannot see WHEN Courier needs them and WHAT exact action unblocks it.
There is no central "Braucht dich" surface; needs-you information is scattered
across policy docs written for agents.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- `docs/META_DISPATCH_AND_RETRY_POLICY.md:89-96` defines HUMAN_ACTION_REQUIRED
  classes (login/2FA/billing/approval/...), and `:140-147` defines central
  operator messages — but the taxonomy has 0 implementations in `server/`+`scripts/`
  (no RETRY_IMMEDIATE/HUMAN_ACTION_REQUIRED/RESOURCE_GUARD strings in code).
- Server task states (`server/app.py:332,378,502` + reclaim/verify paths) are
  QUEUED/DISPATCHED/RESULT_RECEIVED/RECONCILED/FAILED_TERMINAL/FAILED_VERIFICATION.
  No state maps a failure to a user action; FAILED_* carries no "what to do" field.
- Beacon contract notification policy (`docs/COURIER_PROGRESS_BEACON_CONTRACT.md:90-99`)
  is doc-only (see item A: no working beacon).
- Chief relay agent channel EXISTS (`scripts/run_chief_relay_cycle.py`,
  `scripts/consume_chief_command.py`, `schemas/antigravity_worker_job.schema.json`
  all present) — but that is agent↔chief, not user-facing.
- Playbook Phase 6 lists "Braucht dich" as visible pilot minimum
  (`ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:247-254`) — prep only.

## ACCEPTANCE_REQUIREMENT
B-1: Every condition that needs the user (auth, approval, payment, BLOCKED goal,
  FAILED_* task, resource guard, expired lease) MUST produce exactly one durable,
  user-readable needs-you record: WHAT waits, WHY, EXACT action, safe-to-ignore?
  (yes/no), expiry/else-consequence.
B-2: Records MUST be file-first (durable, pollable without a server) OR served from
  a real route — decided once, not both half-built.
B-3: No prompt storms: one record per underlying condition; repeats only on state
  change (per META_DISPATCH central-message philosophy).

## MISSING_SYSTEM_SUPPORT
- Needs-you record (file schema or endpoint) — nothing exists at runtime.
- Mapping server FAILED_*/stale states → user actions.
- Channel decision (status file vs API route) — needs pilot-prep owner decision.

## PREPARABLE_NOW (no code, this pass)
- Needs-you record schema + draft state→action mapping table (static, in a follow-up
  edit once server error vocabulary is frozen).

## BLOCKED_UNTIL
- Server state vocabulary stable (post Core Freeze); channel choice by pilot owner.
- Rollout gated on pilot signal (item J).

## NEXT
C — safe Retry/Restart (item C file).
