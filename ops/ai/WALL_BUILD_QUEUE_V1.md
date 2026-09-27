# Wall System Build Queue V1

Status: ACTIVE BUILD QUEUE
QUEUE_GENERATION=WALL-BUILD-V1

Purpose: prepare exact implementation packets for the MD-first wall, Extended Ledger, Harvester and low-cost provider execution.

## Rules

- No broad repo scan.
- Use exact inputs.
- Reuse earlier WBUILD results.
- Google/docs workers do not edit application source.
- Windows Antigravity Central Writer owns application source changes.
- MAX_HEAVY_JOBS=1.
- Completed WBUILD tasks do not repeat unless their RETEST_TRIGGER changes.

## Tasks

### WBUILD-001 Stable truth resolver
Inputs:
- ops/ai/WALL_SYSTEM.md
- docs/COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md
- docs/CANONICAL_COMPLETION_HANDOFF.md
Done:
- deterministic repo-root/truth resolution packet
- no-human-path acceptance cases

### WBUILD-002 Canonical wall pointer model
Inputs:
- ops/ai/WALL_QUEUE_CURRENT.md
- WBUILD-001 result
Done:
- stable logical keys + supersession/generation rules

### WBUILD-003 Task packet parser/validator
Inputs:
- ops/ai/WALL_TASK_PACKET_SCHEMA.md
Done:
- exact validation rules and invalid-task cases

### WBUILD-004 Queue generation manifest
Inputs:
- WBUILD-002
- WBUILD-003
Done:
- generation schema and dependency representation

### WBUILD-005 Atomic claim/lease
Inputs:
- WBUILD-004
- existing claim/lease semantics only if explicitly needed
Done:
- atomic claim, lease expiry, stale claim, owner identity packet

### WBUILD-006 Compact result contract
Inputs:
- WBUILD-003
- ops/ai/RETURNED_RESULT_POLICY.md
Done:
- result schema, evidence refs, do-not-repeat fingerprint

### WBUILD-007 Harvester algorithm
Inputs:
- WBUILD-005
- WBUILD-006
Done:
- validate -> dedup -> evidence -> reconcile -> unlock dependency algorithm

### WBUILD-008 Extended Execution Ledger fields
Inputs:
- WBUILD-002..007
- ops/ai/GOOGLE_LEDGER_MUSE_WALL_BUILD_PACK_2026-09-27.md
Done:
- final canonical Ledger field/state packet

### WBUILD-009 NEXT_READY resolver
Inputs:
- WBUILD-004
- WBUILD-007
- WBUILD-008
Done:
- deterministic dependency-safe READY rule

### WBUILD-010 Queue refresh
Inputs:
- WBUILD-007..009
Done:
- one-preparer refresh lock and no-broad-scan refresh rule

### WBUILD-011 Do-not-repeat/retest
Inputs:
- WBUILD-006
- WBUILD-008
Done:
- input fingerprint + explicit RETEST_TRIGGER semantics

### WBUILD-012 Session/context continuity
Inputs:
- WBUILD-006..011
- ops/ai/MUSE_STARTUP_AND_CLEAR_RULE_2026-09-26.md
Done:
- checkpoint -> clear/new session -> resume proof packet

### WBUILD-013 Provider/account continuity
Inputs:
- WBUILD-008..012
- ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md
Done:
- account/session change does not change task identity or repeat work

### WBUILD-014 Cost ledger / quota guard
Inputs:
- WBUILD-008
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md
Done:
- estimated/known cost, budget state, quota state, stop/fallback semantics

### WBUILD-015 Device admission controller
Inputs:
- WBUILD-008
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
Done:
- requested/admitted/active/guarded/reserved state machine

### WBUILD-016 Noninterference ownership
Inputs:
- WBUILD-005
- WBUILD-015
Done:
- process/task ownership boundaries and peer safety rules

### WBUILD-017 Google adapter
Inputs:
- WBUILD-003..016 results
- ops/ai/GOOGLE_WINDOWS_CONTINUOUS_WORKER.txt
Done:
- minimum adapter contract for Google worker sessions

### WBUILD-018 Muse adapter
Inputs:
- WBUILD-003..016 results
- ops/ai/MUSE_STARTUP_AND_CLEAR_RULE_2026-09-26.md
Done:
- minimum adapter contract for Muse sessions

### WBUILD-019 Cross-host portability
Inputs:
- WBUILD-017
- WBUILD-018
Done:
- Mac/Windows path abstraction and host-local scratch rules

### WBUILD-020 One-prompt role selection
Inputs:
- WBUILD-004..019
- ops/ai/UNIVERSAL_MD_WALL_MASTER_PROMPT.txt
Done:
- PREPARER/EXECUTOR/HARVESTER role-lock algorithm

### WBUILD-021 Cost regression tests
Inputs:
- WBUILD-010..015
Done:
- tests for no repeated repo census, no idle analysis, result reuse, queue-empty IDLE

### WBUILD-022 Continuity tests
Inputs:
- WBUILD-011..013
Done:
- /clear/new session/restart/manual-authorized-account-change continuity tests

### WBUILD-023 Claim/duplicate tests
Inputs:
- WBUILD-005..007
Done:
- competing workers, stale lease and duplicate-result cases

### WBUILD-024 Truth resolution tests
Inputs:
- WBUILD-001
- WBUILD-002
Done:
- moved repo, stale path, superseded truth, conflict cases

### WBUILD-025 Admission tests
Inputs:
- WBUILD-015
Done:
- requested 10 / admitted 4..10 without queue loss

### WBUILD-026 Harvester tests
Inputs:
- WBUILD-007
- WBUILD-009
Done:
- result -> reconcile -> next READY -> refill proof

### WBUILD-027 Central Writer implementation packet
Inputs:
- WBUILD-001..026 results only
Done:
- deduplicated file/function/change/test packet
- no source reread unless one exact unresolved location remains

### WBUILD-028 Muse wall queue generator
Inputs:
- WBUILD-017..027
- existing durable project results
Done:
- 30-50 logical Muse READY tasks with exact inputs and done conditions

### WBUILD-029 Universal wall proof plan
Inputs:
- WBUILD-020..028
Done:
- exact 1+2+1 bootstrap proof then same-prompt 4-worker proof

### WBUILD-030 Morning handoff
Inputs:
- WBUILD-001..029 result summaries only
Done:
- LEDGER_READY
- HARVESTER_READY
- ONE_PROMPT_READY
- COST_GUARD_READY
- CENTRAL_WRITER_PACKET_READY
- OPEN/BLOCKED/NEXT

## End condition

When WBUILD-030 is complete, do not invent WBUILD-031.
The next generation must come from changed canonical truth or explicit implementation/test results.
