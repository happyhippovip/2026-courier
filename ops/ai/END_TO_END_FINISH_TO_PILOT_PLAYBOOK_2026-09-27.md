# Courier End-to-End Finish-to-Pilot Playbook — 2026-09-27

Status: OPERATOR PLAYBOOK / CURRENT CRITICAL PATH
Purpose: let the operator keep Courier moving without repeatedly asking "what next?"

## North Star

Finish before expansion.

Current product promise:
Courier brings the user back the next day exactly where they left off.

The system must prove that promise before broad product expansion.

## Permanent laws

- NO_EVIDENCE_NO_PASS
- CONTINUE_BY_DEFAULT
- FEATHERLIGHT_BY_DEFAULT
- NO_BUSYWORK
- RESULT_REUSE_FIRST
- MINIMUM_NECESSARY_READS
- one mutable scope = one active writer
- queue empty = truthful IDLE
- session memory is cache; repo/Ledger/task packets are durable truth
- do not repeat completed work unless an explicit RETEST_TRIGGER exists
- expensive/rare model review only when deterministic evidence is insufficient

## Current durable authority

Accepted repair base:
candidate-b-1
4c1e24ccc522042af826bc4c2b595daf85d097f9

Rejected:
candidate-b-2
83940de3d7d33776a712e7506aa76726d16f8587

candidate-b-3 is NOT required.

Windows Antigravity Central Writer remains the only final-candidate application source writer unless newer canonical truth explicitly changes ownership.

Final candidate write scope is exactly:

- scripts/courier_verifier.py
- scripts/integration_contract.py
- tests/test_artifact_upload_flow.py
- server/app.py
- tests/test_p3_server_idempotency.py

## PHASE 0 — Finish wall control plane / Extended Ledger preparation

Goal:
Finish the MD-first wall build queue and turn prior Google/Muse work into durable, deduplicated implementation packets.

Use:
ops/ai/WALL_BUILD_QUEUE_V1.md
ops/ai/WALL_SYSTEM.md
ops/ai/WALL_QUEUE_CURRENT.md

Completion target:
WBUILD-001..030 complete or explicitly BLOCKED with one causal blocker.

Required outputs include:
- stable truth resolver
- task packet contract
- queue generation
- atomic claim/lease
- compact result contract
- Harvester algorithm
- Extended Execution Ledger fields
- deterministic NEXT_READY
- queue refresh
- do-not-repeat/retest
- context/session continuity
- provider/account continuity
- cost/quota guard
- device admission
- noninterference ownership
- Google/Muse adapters
- cross-host portability
- one-prompt role selection
- targeted acceptance packets
- Central Writer implementation packet
- universal wall proof plan
- morning/final handoff

Do not invent WBUILD-031 automatically.

Exit when:
LEDGER_READY / HARVESTER_READY / ONE_PROMPT_READY / CENTRAL_WRITER_PACKET_READY are known, or a concrete blocker is persisted.

## PHASE 1 — Final canonical five-file candidate

Owner:
Windows Antigravity Central Writer only.

Input:
deduplicated Central Writer packet from durable wall results.

Rules:
- base on candidate-b-1
- modify only the five authorized files
- smallest causal changes only
- no unrelated cleanup
- no scope expansion
- no source changes from Mac/Muse/Google support lanes

Required 12-case acceptance surface:

1. task-owned expected hash survives Goal -> Claim -> Pending Verification
2. correct server bytes PASS
3. wrong server bytes FAIL
4. worker-controlled expected hash rejected
5. worker omission does not bypass task expectation
6. no task expectation remains legacy integrity only, not exact-content
7. malformed/ambiguous target FAIL
8. identical replay ACK, including persistence/reload where relevant
9. changed status is not duplicate success
10. changed worker is not duplicate success
11. changed attempt/dispatch generation rejected
12. changed artifact result is not duplicate success

Exit evidence:
FINAL_SHA
BASE_SHA
EXACT_CHANGED_FILES
TARGETED_TEST_COMMANDS
TARGETED_TEST_RESULTS
SKIPPED=0
UNEXPECTED_CHANGED_FILES=0

## PHASE 2 — Independent code-grounded review

Only after PHASE 1 evidence exists.

Reviewer:
Codex HIGH exactly once unless a concrete new delta invalidates that review.

Review only:
- exact final SHA
- exact five-file diff
- 12-case acceptance surface
- trusted-content rule
- replay/duplicate equivalence
- failure semantics
- physical proof readiness

No new architecture.

Exit:
READY_FOR_PHYSICAL_RUN=YES
or exact blocking defect.

If blocked:
send only the smallest blocking defect back to Windows Central Writer.
After any source delta, rerun only the evidence invalidated by that delta.

## PHASE 3 — Physical RUN_1 on Mac

Owner:
Mac Antigravity physical proof runner.

Preconditions:
- exact final SHA known
- final five-file scope proven
- targeted tests green with no skipped tests
- independent review green
- Mac resource admission rechecked
- one heavy physical slot only
- isolated RUN_1 server/worker/verifier/state/artifact/log/workspace
- exact runtime bound to final SHA
- Muse mode is actual Muse mode where required
- worker/verifier keys are distinct and secure
- no reuse of old 8080/live runtime

Required proof:

ONE GOAL
-> A executes exactly once
-> real Result A
-> task-owned expected content hash
-> server-side bytes checked
-> verify PASS
-> A RECONCILED
-> B becomes legal only after A verification
-> B automatically dispatched/started
-> B completes
-> HUMAN_RELAY_COUNT=0
-> no FAILED execution

If any FAILED execution occurs:
RUN_1 FAIL.
Do not retry it into a fake PASS.
Persist evidence and stop for causal repair.

## PHASE 4 — Physical RUN_2 restart / no replay

Only after RUN_1 PASS.

Use fresh isolation.

Required proof:

A executes once
-> Result A persisted while verifier/reconcile path is interrupted as defined
-> checkpoint evidence
-> controlled restart
-> same A result preserved
-> A does NOT re-execute
-> A reconciles
-> B automatically starts
-> B completes
-> A execution count remains 1

Exit:
restart/no-replay proof bound to exact final SHA/runtime.

## PHASE 5 — Core freeze

Now close Gate 1-4 truthfully.

Required:
- Trusted Ledger PASS then LEDGER_FROZEN=YES
- Reliable Motor PASS
- Result -> Verify -> Reconcile -> NEXT_READY proven
- Zero-Human A->B physical proof
- Restart matrix PASS
- Autonomy Grade A4 for the declared Covered Surface
- bounded resource operation
- no tight polling
- Proof Cards
- Source/Build/Runtime/Covered-Surface fingerprints
- no gate-violating UNKNOWNs

Then:
CORE_FREEZE

Do not keep changing Core because models have spare capacity.

## PHASE 6 — Minimal real pilot preparation

This may be prepared in parallel, but it must not destabilize PHASE 0-5.

The first pilot does NOT require a polished Product Shell or automatic installer.

Visible minimum:
- Arbeitet
- Braucht dich
- Fertig
- Proof Card
- Proof Level
- Autonomy Grade
- next action

Manual/onboarding setup is allowed and measured.

Prepare:
- 3-5 real pilot candidates with the exact problem Courier solves
- Goal Contract template
- baseline questionnaire
- pilot duration
- permission/data scope
- deletion/retention note
- provider/data-flow inventory
- simple payment route if paid external pilot
- setup-time measurement
- support-time measurement
- provider-cost measurement

Before a paid external pilot, verify the relevant payment/privacy/tax/business prerequisites. Legal/tax specifics may require professional guidance.

## PHASE 7 — First 5-person pilot cohort

Test only the core promise.

Measure:
HIPG = necessary human continuation interventions / completed or terminated Goals
Target: < 1.0

RSR = passed defined restart scenarios / executed defined restart scenarios
Target: 100%

NDR = user voluntarily returns next day / cohort size

First cohort decision:
3-5 / 5 NDR -> positive signal
2 / 5 -> one bounded iteration, then remeasure
0-1 / 5 -> review core promise/use case/segment; do not auto-build features

Also record:
PAYMENT_YES/NO
actual amount
SETUP_MINUTES_PER_PILOT
support effort
provider cost

## PHASE 8 — Product Shell only after positive pilot signal

Then build the simplest customer path:

Connect
-> Goal
-> Arbeitet
-> Braucht dich
-> Fertig

Optional:
Details

Keep Ledger/Attempt/Execution machinery internal unless the user needs it for trust.

No giant dashboard.

## PHASE 9 — Packaging / updates

Only after Core + pilot proof.

Required later:
- reproducible build
- Source identity
- Build identity
- Loaded-runtime identity
- Single Instance
- signed/safe update
- rollback
- Last Known Good
- state compatibility
- no lost in-flight work

Then the previously recorded automatic/daily update goals can move from LATER into implementation.

## PHASE 10 — Expansion after proof

Only after the above evidence supports expansion:

- wider connector/platform support
- exact selectable wall 1..64
- free-package starter wall sizes
- larger provider routing
- Courier Brain
- broader world/community concepts
- scaled distribution/sales

Do not let these reopen Core without a real causal need.

## Operator return rule

The human should normally return to Chief only for:

- FINAL_SHA + targeted test gate
- Codex blocking defect or READY_FOR_PHYSICAL_RUN
- RUN_1 result
- RUN_2 result
- genuine HUMAN/MONEY/SAFETY/PERMISSION decision
- pilot decision signal

Ordinary executor chatter stays in durable result files.

## What to do when a worker says NO_READY_TASKS

Do not broad-scan.

Order:
1. harvest unprocessed durable results
2. refresh queue exactly once from canonical truth + result summaries + explicit writer handoff + open Ledger blockers
3. if a concrete READY task appears, claim it
4. if still empty, enter truthful IDLE
5. do not consume model tokens merely to avoid IDLE

## What to do after /clear / restart

Paste the permanent finish-to-pilot prompt.

The new session must:
read durable state
determine first incomplete phase
resume the smallest authorized task
never reconstruct the whole history from chat
