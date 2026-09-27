# Ledger Finish Queue 30 — Mac + Windows Google — 2026-09-27

Status: ACTIVE / COST-SENSITIVE / READ_ONLY_SUPPORT
Purpose: finish the Extended Execution Ledger specification, evidence surface, deterministic continuation contract, and Central Writer implementation packet without broad repo rediscovery.

## Hard rules

- RESULT_REUSE_FIRST=YES
- MINIMUM_NECESSARY_READS=YES
- NO_BROAD_REPO_SCAN=YES
- NO_BUSYWORK=YES
- NO_DUPLICATE_REVIEW=YES
- APPLICATION_SOURCE_WRITE=NO
- FINAL_CANDIDATE_WRITE=NO
- MAX_HEAVY_JOBS=1 per host
- Google workers produce specs, evidence, gaps, targeted-test plans, and implementation packets only.
- Existing durable evidence closes tasks without redoing work.
- Credentials/secrets/raw payment data must never enter Ledger or repo.
- One live claim per task.
- Mac and Windows may consume the same logical queue; host does not reset task completion.

## Exact primary inputs

Use only as needed:
- ops/ai/GOOGLE_LEDGER_MUSE_WALL_BUILD_PACK_2026-09-27.md
- ops/ai/WALL_BUILD_QUEUE_V1.md
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
- ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md
- schemas/thought_coverage_ledger.schema.json
- scripts/integration_contract.py only when a task explicitly needs existing field names
- server/app.py only when a task explicitly needs current persistence/result identity behavior

## Queue

### GLEDGER-101 — Canonical entity chain
Map exact durable entity chain:
GOAL -> CONTRACT -> TASK -> ATTEMPT -> CLAIM/LEASE -> DISPATCH -> EXECUTION -> RESULT -> VERIFY -> RECONCILE -> NEXT_READY.
Done: canonical IDs + parent/child references + no ambiguous ownership.

### GLEDGER-102 — Goal/Contract fields
Define minimum Goal and Goal-Contract fields needed for durable acceptance.
Done: required/optional/forbidden fields.

### GLEDGER-103 — Task fields
Define minimum Task fields including dependencies, acceptance, trusted expected content, owner scope.
Done: canonical Task record.

### GLEDGER-104 — Attempt/dispatch identity
Define attempt_id and dispatch_generation semantics.
Done: exact uniqueness/retry rules.

### GLEDGER-105 — Claim/lease fields
Define worker/provider/claimed_at/lease_until/recovery ownership.
Done: canonical claim/lease record.

### GLEDGER-106 — Execution record
Define execution lifecycle and terminal/nonterminal states.
Done: state machine + invalid transitions.

### GLEDGER-107 — Result identity
Define canonical Result identity and result_fingerprint fields.
Done: duplicate-equivalence boundary.

### GLEDGER-108 — Artifact evidence
Define artifact evidence refs and task-owned expected_sha256 placement.
Done: worker input cannot become trusted expectation.

### GLEDGER-109 — Verification record
Define verifier identity, checked evidence, PASS/FAIL/UNKNOWN, timestamp/binding.
Done: no evidence -> no PASS.

### GLEDGER-110 — Reconciliation record
Define Result->Verify->Reconcile transition and ledger effects.
Done: deterministic reconciliation outcome fields.

### GLEDGER-111 — NEXT_READY contract
Define exact dependency-safe NEXT_READY eligibility.
Done: deterministic selection inputs and stop conditions.

### GLEDGER-112 — Queue generation
Define generation_id, truth/result fingerprints, supersession, migration.
Done: no session-reset semantics.

### GLEDGER-113 — Do-not-repeat fingerprint
Define what inputs form do_not_repeat fingerprint.
Done: explicit RETEST_TRIGGER invalidation rules.

### GLEDGER-114 — Stale evidence handling
Define candidate/runtime/generation binding and stale-result rejection.
Done: current-vs-stale decision table.

### GLEDGER-115 — Contradictory result handling
Define same task/generation with non-equivalent result behavior.
Done: never duplicate-ACK contradictions.

### GLEDGER-116 — Provider route fields
Define provider, model/capability, auth_mode reference, route decision fields.
Done: no credential material.

### GLEDGER-117 — Cost/quota state
Define estimated/known cost, quota state, stop/fallback fields.
Done: subscription-first and explicit PAYG fallback semantics.

### GLEDGER-118 — Device/wall state
Define requested/admitted/active/guarded/reserved/heavy/workload fields.
Done: truthful wall capacity representation.

### GLEDGER-119 — Context/session continuity
Define checkpoint/ref, last_progress_at, resume semantics.
Done: /clear/new session/account change cannot duplicate completed work.

### GLEDGER-120 — Stop/block/throttle reasons
Canonicalize stop reasons: HUMAN/MONEY/SAFETY/PERMISSION/RESOURCE/QUOTA/TRUTH/OWNERSHIP/IDLE.
Done: explicit machine-readable set.

### GLEDGER-121 — Security/redaction boundary
Define fields forbidden from Ledger: secrets, raw credentials, auth cookies, raw card/bank data.
Done: redaction/storage policy.

### GLEDGER-122 — Customer projection
Define minimal customer-facing projection from internal Ledger.
Done: Arbeit / Braucht dich / Fertig / Proof / Next without leaking internals.

### GLEDGER-123 — Owner/debug projection
Define owner-facing read-only observability projection.
Done: useful debugging fields without exposing secrets.

### GLEDGER-124 — Schema gap map
Compare canonical Ledger spec against schemas/thought_coverage_ledger.schema.json.
Done: EXISTS/MISSING/AMBIGUOUS only.

### GLEDGER-125 — Integration-contract gap map
Compare canonical fields against scripts/integration_contract.py field names only.
Done: exact gap list, no patch.

### GLEDGER-126 — Server persistence gap map
Inspect only current result/persistence identity points in server/app.py if required.
Done: exact persistence gaps tied to Ledger contract.

### GLEDGER-127 — Acceptance test matrix
Produce targeted acceptance cases for Ledger fields/state/continuity/dedupe/NEXT_READY.
Done: exact tests needed, no broad suite.

### GLEDGER-128 — Harvester contract
Specify validate -> dedup -> evidence -> reconcile -> unlock -> NEXT_READY.
Done: deterministic algorithm and contradiction/stale handling.

### GLEDGER-129 — Central Writer implementation packet
Use GLEDGER-101..128 results only.
Done: FILE/FUNCTION/FIELD_OR_STATE/REQUIRED_CHANGE/TEST/DO_NOT_CHANGE.
No source reread unless one exact unresolved location remains.

### GLEDGER-130 — Ledger finish gate
Use result summaries only.
Output:
LEDGER_SPEC_READY=
HARVESTER_READY=
NEXT_READY_READY=
CONTINUITY_READY=
COST_GUARD_READY=
SECURITY_BOUNDARY_READY=
CUSTOMER_PROJECTION_READY=
CENTRAL_WRITER_PACKET_READY=
OPEN=
BLOCKED=
NEXT=

Do not invent GLEDGER-131 automatically.

## Result record

TASK_ID=
STATUS=PROVEN|OPEN|BLOCKED|OBSOLETE|CONTRADICTED|NEEDS_VERIFICATION
HOST=
PROVIDER=
INPUTS_READ=
RESULTS_REUSED=
OUTPUT_REF=
MISSING=
BLOCKER=
NEXT_DEPENDENCY=
DO_NOT_REPEAT_FINGERPRINT=

## End condition

When GLEDGER-130 is complete:
- if Central Writer packet is READY, hand it to the existing authorized writer path;
- if exact blockers remain, persist only those blockers;
- otherwise LEDGER_PREP_COMPLETE=YES.
No filler queue.
