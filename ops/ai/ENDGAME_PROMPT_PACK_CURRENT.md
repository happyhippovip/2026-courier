# Courier Endgame Prompt Pack — CURRENT

Date: 2026-09-28
Use with: ops/ai/GATE_STATE_CURRENT.md and ops/ai/ENDGAME_SLOT_ROUTER_CURRENT.md

This pack is intentionally phase-aware. Do not run later-phase prompts before the durable gate moves.

## P0 — Generic returning Muse window

COURIER — RETURNING WINDOW ROUTER

SLOT_ID=<01..30>
HOST=<MAC|WINDOWS>
PROVIDER=MUSE
MODE=READ_ONLY
NO_SOURCE_WRITES=YES
NO_PHYSICAL_RUNS=YES
NO_LEDGER_WORK=YES

Read:
ops/ai/GATE_STATE_CURRENT.md
ops/ai/ENDGAME_SLOT_ROUTER_CURRENT.md

Determine CURRENT_PHASE, CURRENT_SHA, ASSIGNED_LANE.

If this slot is active in the current phase:
- finish the entire assigned lane;
- reuse unchanged evidence;
- do not stop after one PASS/FAIL/subcase;
- checkpoint every distinct result;
- if source change needed, create exact WRITER_PACKET only;
- if physical run needed, create exact PHYSICAL_PACKET only.

If this slot is PARKED:
do not invent work.

Return only:
SLOT_ID=
CURRENT_PHASE=
CURRENT_SHA=
ASSIGNED_LANE=
LANE_COMPLETE=
WAITING_FOR=
NEXT_TRIGGER=

## P1 — Sole writer, current BEFORE_RUN1 source gate

COURIER — FINAL SERIAL SOURCE WRITER

ROLE=SOLE_WINDOWS_CENTRAL_WRITER
SOURCE_WRITE=YES
SOLE_WRITER=YES
NO_PHYSICAL_RUN=YES
NO_LEDGER_WORK=YES

Read:
ops/ai/GATE_STATE_CURRENT.md
ops/ai/ENDGAME_SLOT_ROUTER_CURRENT.md
latest confirmed writer packets

Base recovered candidate:
runner-recovery/e9b4f15f-20260928
e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939

Mission:
close the entire CURRENT BEFORE_RUN1 source gate.

Candidate blocker families, only if confirmed on current bytes:
- verifier/key-custody independence
- N1 stale execute_run1 path
- N2 RUN1->RUN2 gate
- stale RUN1-success authorization
- SHA/RUN_ID/result/verifier binding
- transition/result provenance
- DONE->SUCCESS false-green
- human relay truth
- RUN2 simulation/desimulation

For each:
confirm -> smallest causal fix -> targeted positive/negative tests -> relevant regressions -> commit/checkpoint -> next blocker.

Do not stop after first fix.
Do not refactor unrelated code.
Do not run RUN1/RUN2.

Stop when REMAINING_CONFIRMED_SOURCE_BLOCKERS=0 or a hard owner dependency exists.

Return:
BASE_SHA=
FINAL_SHA=
COMMITS=
FILES_CHANGED=
FIXED_BLOCKERS=
DISPROVEN_BLOCKERS=
TARGETED_TESTS=
REGRESSION_TESTS=
TEST_RESULT=
REAL_PRODUCER_SOURCE_READY=
RUN1_SOURCE_READY=
RUN2_SOURCE_READY=
REMAINING_CONFIRMED_SOURCE_BLOCKERS=
NEXT_PHASE=POST_WRITER_NEW_SHA_CONVERGENCE

## P2 — All read-only windows after writer SHA

COURIER — POST-WRITER CHANGED-BYTES SWARM

SLOT_ID=<01..30>
MODE=READ_ONLY
NO_SOURCE_WRITES=YES
NO_PHYSICAL_RUNS=YES
NO_LEDGER_WORK=YES

Read:
ops/ai/GATE_STATE_CURRENT.md
ops/ai/ENDGAME_SLOT_ROUTER_CURRENT.md
latest sole-writer closeout

Determine OLD_SHA, NEW_SHA, ASSIGNED_LANE.

Do not rerun full historical review.

For previous evidence classify:
REUSABLE
INVALIDATED_BY_NEW_SHA
ACTUAL_RUNTIME_REQUIRED

Finish every distinct legal subcase in ASSIGNED_LANE against NEW_SHA.
Use existing evidence first.
If another current checkpoint conclusively covers same subcase, choose another unfinished subcase inside the lane.

Return:
SLOT_ID=
NEW_SHA=
ASSIGNED_LANE=
PROVEN=
DISPROVEN=
UNKNOWN=
WRITER_PACKET=
PHYSICAL_PACKET=
LANE_COMPLETE=
RUN1_IMPACT=
RUN2_IMPACT=
NEXT_TRIGGER=

## P3 — Mac exact binding

COURIER — FINAL MAC EXACT BINDING

ROLE=MAC_BINDING_OWNER
NO_SOURCE_WRITE=YES
NO_PHYSICAL_RUN_YET=YES

Read current gate and post-writer convergence.

Require:
REAL_PRODUCER_SOURCE_READY=YES
RUN1_SOURCE_READY=YES

Bind exact candidate:
FINAL_SHA=
REMOTE_SHA=
LOCAL_SHA=

Require exact equality and reviewed runner bytes.

Prepare:
fresh RUN_ID
fresh state directory
fresh evidence directory
exact runner entrypoint
exact task A/B
independent verifier credentials
PID/PGID ownership
port ownership
resource admission
foreign processes untouched
MAX_HEAVY_JOBS=1

Do not execute RUN1.

Return:
BOUND_SHA=
MAC_BINDING_READY=
RUN1_PREP_COMPLETE=
ENTRYPOINT=
STATE_DIR=
EVIDENCE_DIR=
NEXT_PHASE=RUN1_ACTUAL

## P4 — Actual RUN1

COURIER — ACTUAL PHYSICAL RUN1

ROLE=SINGLE_PHYSICAL_OWNER
NO_RETRY_TO_PASS=YES

Require:
MAC_BINDING_READY=YES
REAL_PRODUCER_SOURCE_READY=YES
RUN1_SOURCE_READY=YES

Execute exactly one fresh RUN1 identity.

Prove:
A execution count=1
real effect occurred
Result A belongs to A execution
artifact bytes belong to A
task-owned expected hash
server stores exact bytes
independent verifier rehashes exact bytes
reconcile
NEXT_READY
B auto-dispatch
B auto-start
B complete
HUMAN_RELAY_COUNT=0
FAILED_EXECUTIONS=0

Any failure:
RUN1_RESULT=FAIL
persist exact evidence
STOP
No retry-to-pass.

On success:
RUN1_RESULT=PASS
persist SHA/run/evidence fingerprints
NEXT_PHASE=RUN2_ACTUAL

## P5 — Actual RUN2

COURIER — ACTUAL PHYSICAL RUN2

ROLE=SINGLE_PHYSICAL_OWNER
REQUIRE_RUN1_PASS=YES
NO_RETRY_TO_PASS=YES

Use the same proven candidate SHA.

Perform controlled restart.

Prove:
A persisted
A not re-executed
A execution count remains exactly 1
A not falsely newly verified
B can continue legitimately
stale dispatch rejected
stale result rejected
stale worker rejected
stale attempt rejected
zero human relay

Any unexpected A execution => RUN2_RESULT=FAIL and STOP.

On success:
RUN2_RESULT=PASS
persist exact evidence fingerprint
NEXT_PHASE=CORE_FREEZE

## P6 — Core Freeze swarm

COURIER — CORE FREEZE SLOT

SLOT_ID=<01..30>
MODE=READ_ONLY
NO_SOURCE_WRITES=YES
NO_PHYSICAL_RUNS=YES

Read:
ops/ai/GATE_STATE_CURRENT.md
ops/ai/ENDGAME_SLOT_ROUTER_CURRENT.md
actual RUN1 evidence
actual RUN2 evidence

Use the CORE_FREEZE slot routing.

PREP_ONLY != PROVEN.

Close assigned requirement using exact runtime/source fingerprints.

If requirement fails:
produce smallest exact owner packet.

Return:
SLOT_ID=
REQUIREMENT=
VERDICT=PROVEN|FAIL|UNKNOWN
EVIDENCE=
BLOCKER=
OWNER=
LANE_COMPLETE=

## P7 — Core Freeze decision owner

COURIER — CORE FREEZE FINAL DECISION

MODE=READ_ONLY_DECISION
NO_NEW_FEATURES=YES

Consume all current Core Freeze slot results plus actual RUN1/RUN2 evidence.

Require:
Ledger frozen
Real Producer proven
independent verifier proven
Result->Verify->Reconcile->NEXT_READY proven
A->B zero human relay
RUN1 PASS
RUN2 PASS
restart/no replay proven
bounded process/resources
exact evidence fingerprints
no gate-violating UNKNOWN

If all proven:
CORE_FREEZE=PASS
FROZEN_SHA=
NEXT_PHASE=MINIMUM_REAL_PILOT

Otherwise:
CORE_FREEZE=BLOCKED
EXACT_BLOCKERS=
NEXT_OWNER=

## P8 — Minimum real pilot prep swarm

COURIER — MINIMUM REAL PILOT PREP SLOT

SLOT_ID=<01..12>
MODE=READ_ONLY_OR_DOC_PREP
NO_PRODUCT_SHELL_EXPANSION=YES

Require CORE_FREEZE=PASS.

Use the pilot lane routing:
01 workflow selection
02 onboarding minimum
03 input/output contract
04 customer-visible evidence
05 intervention accounting
06 failure handling
07 support burden
08 provider cost
09 rollback
10 pilot report
11 repeat-use signal
12 Product Shell unlock criteria

Produce a concrete, usable pilot packet for the assigned lane.
No unproven claims.
No fake customer evidence.

## P9 — Product Shell unlock

COURIER — PRODUCT SHELL UNLOCK CHECK

MODE=READ_ONLY_DECISION

Require:
CORE_FREEZE=PASS
PILOT_RESULT=POSITIVE
REPEATED_USE_SIGNAL=YES

If not satisfied:
PRODUCT_SHELL_UNLOCKED=NO
state exact missing evidence.

If satisfied:
PRODUCT_SHELL_UNLOCKED=YES
define the smallest customer-facing shell that exposes proven Courier behavior without adding unproven autonomy.

Return:
PRODUCT_SHELL_UNLOCKED=
PROVEN_CUSTOMER_VALUE=
MINIMUM_SHELL_SCOPE=
DO_NOT_BUILD=
NEXT_OWNER=
