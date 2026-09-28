# Gate State Current — 2026-09-28

Status: DURABLE COORDINATION STATE
UPDATED_FOR_RUNNER_RECOVERY=YES

LEDGER_STATUS=FROZEN_COMPLETE
LEDGER_NEXT_ACTION=NONE_UNLESS_RETEST_TRIGGER

BASE_CANDIDATE_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
RECOVERED_RUNNER_BRANCH=runner-recovery/e9b4f15f-20260928
RECOVERED_RUNNER_SHA=e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939
RECOVERED_RUNNER_REMOTE_VERIFIED=YES
RECOVERED_RUNNER_COMPARE=12_AHEAD_0_BEHIND_FROM_candidate-b-1

CURRENT_PHASE=BEFORE_RUN1_WRITER
AUTHORITATIVE_READY=NO

REASON=
The recovered physical-runner stack is now durable on the remote branch and read-only wall work has substantially converged.
The active critical path is no longer PRE_CODEX or remote-durability validation.
Remaining work is serial: one exact writer pass on confirmed blockers, post-writer changed-byte convergence, exact Mac binding, RUN_1, RUN_2, Core Freeze.

CONFIRMED_OR_ACTIVE_BLOCKER_CLASSES:
- verifier/key-custody independence if still confirmed on current bytes;
- N1 stale execute_run1 reference/test path;
- N2 RUN1->RUN2 gate / unconditional-success false-green risk;
- transition/result provenance;
- synthesized DONE->SUCCESS / relay proof paths if still reachable;
- RUN_2 simulation/desimulation on the proof path.

NEXT=SOLE_WINDOWS_WRITER_CURRENT_BLOCKERS
NEXT_AFTER_WRITER=POST_WRITER_NEW_SHA_CONVERGENCE
NEXT_AFTER_CONVERGENCE=MAC_EXACT_BINDING
NEXT_AFTER_BINDING=SINGLE_PHYSICAL_OWNER_RUN1
NEXT_AFTER_RUN1_PASS=SINGLE_PHYSICAL_OWNER_RUN2
NEXT_AFTER_RUN2_PASS=CORE_FREEZE
NEXT_AFTER_CORE_FREEZE=MINIMUM_REAL_PILOT

MAX_SOURCE_WRITERS=1
MAX_PHYSICAL_MAC_OWNERS=1

READ_ONLY_WALL_STATE=CONVERGED_UNTIL_REAL_STATE_CHANGE

COST_GUARD:
- do not send Muse/Google back to old PRE_CODEX work;
- do not repeat local/remote runner discovery;
- do not repeat acceptance-harness false-proof finding;
- do not reopen Ledger absent RETEST_TRIGGER;
- do not invent new read-only shards merely to keep windows busy;
- park read-only windows until a real trigger appears.

INVALIDATION_TRIGGER:
- writer produces a new SHA;
- actual RUN_1 evidence appears;
- actual RUN_2 evidence appears;
- a proven causal defect invalidates current evidence.

WORKER_RULE:
If CURRENT_PHASE=BEFORE_RUN1_WRITER and this session is not the sole authorized writer,
do not generate more broad review. Reuse existing evidence and stop/park until NEXT_AFTER_WRITER trigger.
