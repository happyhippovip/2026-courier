# CODEX MASTER CONTEXT — 2026-09-26

Status: ACTIVE COORDINATION BRIEF
Purpose: Give Codex the complete currently relevant Courier context without forcing a restart-from-zero review.

## 0. Operating rules

RULE_1 = CONTINUE_BY_DEFAULT
RULE_2 = FEATHERLIGHT_BY_DEFAULT
RULE_3 = THE_GRANDMA_TEST
TRUTH > SPEED
NO_EVIDENCE -> NO_PASS

Do not infer runtime truth from filenames, branch names, or model claims.
Repository/test/runtime evidence decides.

## 1. Current critical path

N1-010 is PARKED.

Do not start a new business-review round.

Current critical path:

1. Close Artifact -> Verify cutover on the chosen integration candidate.
2. Close documented duplicate-detection / duplicate-execution gaps.
3. Bind exact candidate:
   - branch
   - source SHA/fingerprint
   - relevant configuration
   - loaded runtime identity where applicable
   - Muse/provider CLI binding
4. Run targeted tests.
5. Physical one-slot proof on Mac:
   TASK A
   -> REAL RESULT
   -> independent content verification
   -> ACCEPT
   -> TASK B starts automatically
   -> HUMAN_RELAY_A_TO_B = 0
6. Controlled restart proof:
   A must not be blindly replayed.
7. Only then provider authorization + quota/capacity + resource admission for scale.
8. Scale 1 -> 4 -> 8 -> 16.
9. Bounded 60-120+ minute Featherlight soak.
10. Record demo only from real runtime evidence.

No additional architecture is authorized by this brief.

## 2. Three corrected assumptions

### Scheduler authority
Two scheduler source files do NOT prove two active authorities.
Authority is a runtime fact:
which live process/component actually mutates queue, claim, retry and NEXT state?

### Merge safety
Conflict-free Git merge != safe integration.
Mergeability does not prove:
- Artifact->Verify correctness
- duplicate handling
- runtime binding
- physical continuation

### Proof binding
Physical proof belongs to an exact authorized candidate.
It does not have to be main.
Decision-relevant changes require affected evidence to be rechecked.

## 3. Evidence state

KNOWN:
- one physical Windows path has reached RESULT_RECEIVED in supplied evidence
- Mac physical A->VERIFY->B is NOT yet proven
- simulated tests are not physical proof
- demo metrics must be real runtime evidence
- provider authorization/quota/resource admission precede 4/8/16
- benchmark must separate SINGLE_TASK_LATENCY from VERIFIED_CONTINUATION_THROUGHPUT_WITHOUT_HUMAN

UNKNOWN / MUST BE VERIFIED:
- actual live scheduler authority
- current Mac wall/slot/writer/runtime state
- physical Muse CLI protocol/session binding
- provider authorization/quota for multi-slot scale
- real LIGHT/HEAVY task-contract support
- measured idle supervisor overhead
- existence/coverage of durable structured context reuse layer

## 4. Featherlight law

Goal:
maximum verified useful work while the machine still feels normal to use.

The Mac should remain usable for:
- screen recording
- music playback
- browser use
- normal desktop interaction

45 logical slots != 45 heavy processes.

Mac initial heavy budget = 1 until evidence supports a change.
Windows initial heavy budget = 2 until evidence supports a change.

Unknown heavy capacity should block new heavy work.
It should not be interpreted as proof that no useful light work exists; however Codex must first verify whether the real task contract can represent/admit LIGHT vs HEAVY work.

Do not invent a LIGHT/HEAVY contract if it does not exist.

## 5. Corrected performance suspicions

### process_identity / ps overhead
Earlier suspicion that ps runs once per slot per tick was too strong.
Current reading suggests supervisor-owned children can be checked through existing process handles; ps is more relevant to spawn/adoption/reconciliation.
Treat overhead as a measurement target, not a proven multiplier.

Measure/inspect:
- IDLE_CPU_OVERHEAD
- PROCESS_SPAWNS_PER_TICK
- SUPERVISOR_TICK_COST
- SLOT_COUNT_SCALING

### context reuse
Repeated repo reconstruction was observed in at least one development log.
Absence of a durable context/knowledge layer has NOT been systematically proven.

Verify before concluding.

Potential reusable knowledge categories:
- repo map
- branch inventory
- known findings
- test inventory
- provider capabilities
- host capabilities
- prior verified failures

## 6. Human-understanding / Grandma Test

The product is not clear enough if a non-technical person cannot understand what was accomplished.

Daily visible summary must answer:
- AUFTRAG
- ERLEDIGT
- BEWEIS
- MENSCH MUSSTE EINGREIFEN
- ALS NÄCHSTES

Tomorrow Test:
"What can I show tomorrow that did not exist yesterday?"

The demo is NOT successful merely because many terminals are visible.

The demo must show:
- what was asked
- what finished
- what was independently checked
- how many human interventions were required
- what started next automatically

No fake or simulated metrics.

## 7. Current product promise

"Du bist im Urlaub. Courier arbeitet weiter."

Operational meaning:
GOAL -> QUEUE -> CLAIM -> WORK -> RESULT -> VERIFY -> NEXT

The human must not become the message bus.

Pause is legitimate only for real gates:
- human approval
- auth/login/2FA/CAPTCHA
- payment/spend
- provider quota/unavailability
- safety/resource gate
- unresolved execution ambiguity
- genuinely completed goal

## 8. Mac / Windows separation

Mac:
- canonical Muse runtime under investigation/proof
- one source writer per write scope
- heavy budget initially 1
- preserve long-running sessions
- do not interrupt healthy workers just to deliver context

Windows:
- Google/Antigravity owns Windows writer scope
- Windows Muse remains read-only while that writer is live
- heavy budget initially 2
- Mac must not remote-control Windows; Windows must not remote-control Mac

Protected / strict read-only in current coordination:
- server/app.py
- server/run_waitress.py
- server/launch_server_hidden.vbs

Do not enable confirmation modes that previously destabilized Antigravity setup.
Do not use account rotation to evade provider limits.
Do not use GitHub Actions for local/simple verification.
Do not force push / reset hard / clean / merge main blindly.

## 9. Canonical runtime files to inspect

At minimum:
- scripts/mac_worker/muse_supervisor.py
- scripts/mac_worker/muse_adapter.py
- scripts/mac_worker/daemon.py
- scripts/mac_worker/runtime_state.py
- scripts/run_autonomous_supervisor.py

Targeted tests:
- tests/test_muse_supervisor.py
- tests/test_muse_convergence.py
- tests/test_mac_worker_recovery.py
- tests/test_mac_worker_contract.py

Do not assume tests are physical proof.

## 10. Required coordination documents

Read in this order:

1. docs/COURIER_CURRENT_CONVERGENCE_CHECKPOINT_2026-09-26.md
2. docs/COURIER_NUMBER_ONE_MASTERPLAN.md
3. docs/COURIER_CONTINUOUS_OPERATION_PROMISE.md
4. docs/COURIER_GRANDMA_TEST.md
5. docs/CANONICAL_COMPLETION_HANDOFF.md
6. docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md
7. ops/ai/CONVERGENCE_REVIEW_ORDER_2026-09-26.json
8. ops/ai/NUMBER_ONE_TASK_SEED_2026-09-26.json
9. ops/ai/VACATION_MODE_TASK_SEED_2026-09-26.json
10. ops/ai/AUTOFILL_TASK_SEED_2026-09-26.json

These documents are coordination/governance, not runtime proof.

## 11. External reviewer roles

Opus:
- convergence / integration
- reconcile contradictions
- choose one minimal implementation sequence
- no new architecture

Codex:
- runtime truth / red-team
- attack assumptions
- identify exact physical blocker
- define minimal delta and proof
- no implementation in review mode

Existing Google/Central writer:
- only implement the final minimal authorized delta
- Artifact/Verify + duplicate gaps first
- no extra architecture

Muse/Google workers:
- continue existing owned work
- preserve long-run evidence
- do not get duplicate prompts while active

## 12. Current report paths

Preferred Mac report paths:
- /Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_CONTINUATION_CONVERGENCE.md
- /Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_FEATHERLIGHT_NUMBER_ONE.md
- /Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_CODEX_FINAL_RECONCILIATION.md
- /Users/user/Downloads/courier_work/muse_burn30/reports/CODEX_NUMBER_ONE_RED_TEAM.md
- /Users/user/Downloads/courier_work/muse_burn30/reports/CODEX_NEXT_VIDEO_RUNTIME_PROOF.md
- /Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_HUMAN_UNDERSTANDING.md

If a path is inaccessible in the current environment:
mark it unavailable.
Do not pretend it was read/written.

## 13. What Codex must do next

Codex must NOT restart from zero.

It must:
1. read the coordination checkpoint and this master context
2. verify claims against repo/tests/runtime evidence
3. explicitly separate:
   - PROVEN
   - UNPROVEN
   - CONTRADICTED
   - UNKNOWN
4. inspect the exact Artifact->Verify cutover gap
5. inspect duplicate gaps
6. identify actual scheduler authority only from runtime/process evidence if available
7. define the smallest writer delta
8. define exact targeted tests
9. define exact bound physical one-slot A->VERIFY->B proof
10. define restart/no-replay proof
11. define provider/quota/resource preflight for 4/8/16
12. define metrics for Featherlight + Grandma Test demo

No implementation in review mode.

## 14. Stop condition for Codex review

The review is complete only when it can produce ONE next writer task with:
- exact scope
- exact files/areas
- exact forbidden scope
- exact acceptance tests
- exact candidate binding
- exact physical proof
- exact stop condition

If evidence is missing, say UNKNOWN instead of inventing it.

N1-010 remains PARKED.
