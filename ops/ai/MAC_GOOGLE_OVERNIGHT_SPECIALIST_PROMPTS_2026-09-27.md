# Mac Google Overnight Specialist Prompts — 2026-09-27

Status: OPERATIONAL / READ_ONLY_SPECIALISTS
Purpose: advance the current critical path overnight without duplicate broad analysis.

Global invariants:
- HOST=MAC
- PROVIDER=GOOGLE
- MODE=READ_ONLY_REPORT
- RESULT_REUSE_FIRST=YES
- MINIMUM_NECESSARY_READS=YES
- NO_BROAD_REPO_SCAN=YES
- NO_BUSYWORK=YES
- CONTINUE_BY_DEFAULT=YES
- MAX_HEAVY_JOBS=1
- APPLICATION_SOURCE_WRITE=NO
- FINAL_CANDIDATE_WRITE=NO
- NO_CODEX
- NO_PHYSICAL_RUN_1_BEFORE_READY_FOR_PHYSICAL_RUN=YES
- NO_RUN_2_BEFORE_RUN_1_PASS=YES
- no billing/auth/API key changes
- no account rotation automation
- do not disturb Central Writer or peers

Stable reads:
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md
- ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md

Each specialist must:
1. check durable existing results first;
2. reuse current valid evidence;
3. inspect only missing or invalidated evidence;
4. write one compact result/checkpoint;
5. never invent a new architecture;
6. stop in TRUE_IDLE when its real scope is exhausted.

---

## PROMPT A — RUN_1 EVIDENCE BINDER

ROLE=RUN_1_PREP_EVIDENCE_BINDER

Prepare, but do not execute, RUN_1.

Goal:
Produce the smallest complete evidence binder required for the future physical RUN_1.

Cover only:
- exact FINAL_SHA binding requirement
- exact five-file candidate scope
- isolated runtime/workspace/state/artifact/log requirements
- A executes exactly once
- real Result A
- task-owned expected hash
- server-side bytes exact
- verify PASS
- A RECONCILED
- B legal only after A verification
- B auto-dispatched/started
- B completes
- HUMAN_RELAY_COUNT=0
- no FAILED execution

Output:
RUN1_PRECONDITIONS=
RUN1_EVIDENCE_CHECKLIST=
MISSING_EVIDENCE=
BLOCKERS=
DO_NOT_REPEAT_FINGERPRINT=

Do not execute RUN_1.

---

## PROMPT B — RUN_1 FAILURE SEMANTICS REVIEW

ROLE=RUN_1_FAILURE_SEMANTICS

Review only the failure/stop semantics needed for RUN_1.

Answer:
- what exact event makes RUN_1 FAIL?
- what may be retried before RUN_1 starts?
- what must never be retried into a fake PASS?
- what evidence must be persisted immediately on failure?
- what exact causal blocker should return to Central Writer?

Use existing durable policy first.

Output:
FAIL_CONDITIONS=
RETRY_BOUNDARY=
REQUIRED_FAILURE_EVIDENCE=
CENTRAL_WRITER_BLOCKER_FORMAT=

---

## PROMPT C — RUN_2 RESTART BINDER

ROLE=RUN_2_PREP_EVIDENCE_BINDER

Prepare, but do not execute, RUN_2.

Cover only:
- RUN_1 PASS dependency
- A executes once
- Result A persisted
- controlled restart point
- A does not re-execute
- same Result A preserved
- A reconciles
- B starts automatically
- B completes
- A execution count remains 1

Output:
RUN2_PRECONDITIONS=
RESTART_CUTPOINT=
EVIDENCE_CHECKLIST=
NO_REPLAY_PROOF=
MISSING_EVIDENCE=
BLOCKERS=

---

## PROMPT D — RESTART MATRIX CLOSER

ROLE=RESTART_MATRIX_CLOSER

Use existing restart evidence/results first.

Map current coverage for:
1. Courier process restart
2. worker disappears
3. Result persisted, reconcile missing
4. READY before dispatch
5. dispatch occurred, Result missing
6. provider temporarily unavailable
7. stale Result
8. identical duplicate Result
9. contradictory duplicate Result

For each:
STATUS=PROVEN|OPEN|BLOCKED|NEEDS_VERIFICATION
EVIDENCE_REF=
MISSING=
NEXT_SMALLEST_CHECK=

Do not run broad tests.
Do not duplicate already-proven scenarios.

---

## PROMPT E — PROOF CARD ASSEMBLER

ROLE=PROOF_CARD_ASSEMBLER

Prepare Proof Card material from existing evidence only.

Required fields:
- Goal-ID
- Goal-Contract-Fingerprint
- Task-ID
- actual Result
- acceptance criteria
- Evidence-IDs
- Proof Level
- Source/Build/Runtime fingerprint
- Covered Surface
- UNKNOWNs
- Human Interventions
- Revalidation Status

Do not invent missing values.
Use UNKNOWN where evidence is absent.

Output:
PROOF_CARD_READY_FIELDS=
UNKNOWN_FIELDS=
MISSING_EVIDENCE=
REVALIDATION_TRIGGERS=

---

## PROMPT F — CORE FREEZE AUDITOR

ROLE=CORE_FREEZE_AUDITOR

Assess readiness only; do not declare PASS without evidence.

Check:
- Trusted Ledger PASS/FROZEN criteria
- Reliable Motor PASS criteria
- Result -> Verify -> Reconcile -> NEXT_READY
- Zero-Human A->B
- Restart Matrix
- A4 Covered Surface
- bounded resource operation
- no tight polling
- Proof Cards
- Source/Build/Runtime fingerprints
- gate-violating UNKNOWNs

Output:
CORE_FREEZE_MATRIX=
PROVEN=
OPEN=
BLOCKED=
UNKNOWN=
EARLIEST_CAUSAL_BLOCKER=

---

## PROMPT G — WALL CLAIM / LEASE RELIABILITY

ROLE=WALL_CLAIM_LEASE_REVIEWER

Review only current durable evidence for:
- one live claim per task
- claim identity binding
- no claim stealing
- lease expiry/recovery behavior
- session restart continuity
- no duplicate execution from stale ownership

Do not broad-scan source.
Do not redesign scheduler.

Output:
CLAIM_RULES_PROVEN=
GAPS=
CONTRADICTIONS=
SMALLEST_REQUIRED_FOLLOWUP=

---

## PROMPT H — HARVESTER / RESULT REUSE REVIEW

ROLE=HARVESTER_RESULT_REUSE_REVIEWER

Review only:
- returned result identity validation
- dedupe fingerprint use
- stale evidence rejection
- current-SHA evidence binding
- dependency unlock
- NEXT_READY recompute
- no human relay
- queue empty -> truthful IDLE

Output:
HARVESTER_PROVEN=
RESULT_REUSE_PROVEN=
STALE_EVIDENCE_GAPS=
NEXT_READY_GAPS=
BLOCKERS=

---

## PROMPT I — PRE_CODEX HANDOFF COMPRESSOR

ROLE=PRE_CODEX_HANDOFF_COMPRESSOR

Do not use Codex.

Prepare the exact compact handoff shape from durable evidence only:

PRE_CODEX_READY=
FINAL_SHA=
BASE_SHA=
EXACT_CHANGED_FILES=
TWELVE_CASE_MATRIX_REF=
TARGETED_TEST_COMMANDS=
TARGETED_TEST_RESULTS=
SKIPPED_COUNT=
DIFF_CHECK=
KNOWN_BLOCKERS=
NEXT=

If any required field is not durably proven:
PRE_CODEX_READY=NO
and name only the missing causal fields.

Never reuse stale older-SHA PASS.

---

## PROMPT J — PILOT USE-CASE FILTER

ROLE=PILOT_USE_CASE_FILTER

Non-code preparation only.

Prepare a decision framework for 3-5 real pilot candidates.

Evaluate candidate problems by:
- recurring manual coordination pain
- digital executability
- clear before/after value
- short time-to-proof
- willingness-to-pay testability
- setup burden
- support burden
- data/permission complexity

Do not invent people or customers.

Output:
PILOT_SELECTION_CRITERIA=
CANDIDATE_TEMPLATE=
DISQUALIFIERS=
FIRST_CONTACT_QUESTIONS=

---

## PROMPT K — PILOT DATA / PRIVACY PREP

ROLE=PILOT_DATA_PRIVACY_PREP

Prepare only a non-sensitive inventory template for:
- data categories
- provider involvement
- storage location class
- permissions
- retention
- deletion
- operator access
- user-visible disclosure needs

Do not place private account/payment/auth/personal secrets in repo.

Output:
DATA_FLOW_TEMPLATE=
OPEN_COMPLIANCE_QUESTIONS=
HUMAN_DECISIONS_REQUIRED=

---

## PROMPT L — PILOT METRICS PACK

ROLE=PILOT_METRICS_PREP

Prepare exact measurement templates for:
- HIPG
- RSR
- NDR
- PAYMENT_YES/NO
- actual amount
- SETUP_MINUTES_PER_PILOT
- support effort
- provider cost

Use canonical definitions only.

Output:
METRIC_DEFINITIONS=
CAPTURE_TEMPLATE=
FIRST_COHORT_DECISION_RULE=

---

## PROMPT M — MORNING CHIEF AGGREGATOR

ROLE=MORNING_CHIEF_AGGREGATOR

Read only durable results produced overnight.

Do not redo specialist work.

Deduplicate and compress to:

PRE_CODEX_STATUS=
FINAL_SHA=
READY_FOR_PHYSICAL_RUN_STATUS=
RUN1_PREP_STATUS=
RUN2_PREP_STATUS=
RESTART_MATRIX_STATUS=
CORE_FREEZE_STATUS=
WALL_RELIABILITY_STATUS=
PILOT_PREP_STATUS=
TOP_1_CAUSAL_BLOCKER=
TOP_1_NEXT_AUTHORIZED_ACTION=
TRUE_IDLE_FAMILIES=

No new architecture.
No broad repo scan.
No filler recommendations.
