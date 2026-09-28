# Gate State Current — 2026-09-28

Status: DURABLE COORDINATION STATE
UPDATED_FOR_RUNNER_RECOVERY=YES
UPDATED_FOR_LATE_STATE_RECONCILIATION=YES

LEDGER_STATUS=FROZEN_COMPLETE
LEDGER_NEXT_ACTION=NONE_UNLESS_RETEST_TRIGGER

BASE_CANDIDATE_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
RECOVERED_RUNNER_BRANCH=runner-recovery/e9b4f15f-20260928
RECOVERED_RUNNER_SHA=e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939
RECOVERED_RUNNER_REMOTE_VERIFIED=YES
RECOVERED_RUNNER_COMPARE=12_AHEAD_0_BEHIND_FROM_candidate-b-1

LOCAL_OBSERVED_FIXED_COMMIT_PREFIX=dfd22bb
LOCAL_OBSERVED_FIXED_COMMIT_FULL_SHA=UNKNOWN_NOT_DURABLE
LOCAL_OBSERVED_FIXED_COMMIT_REMOTE_PRESENT=NO_PER_LOCAL_EVIDENCE
LOCAL_OBSERVED_FIXED_COMMIT_WORKTREE_PRESENT=NO_PER_LOCAL_EVIDENCE
DO_NOT_TREAT_DFD22BB_PREFIX_AS_A_RUN_ID=YES

CURRENT_PHASE=CANDIDATE_STATE_RECONCILIATION
AUTHORITATIVE_READY=NO
PHYSICAL_RUN_AUTHORIZED=NO
CORE_FREEZE_READY=NO

REASON=
Late local evidence conflicts with the older durable gate and with a later local Mac binding report.
Three candidate identities are currently in play:
1. historical/base candidate 34b0a426...;
2. durable recovered runner e9b4f15f... on runner-recovery/e9b4f15f-20260928;
3. a locally observed fixed-but-orphaned commit prefix dfd22bb with no durable branch/worktree according to the latest local evidence.
A physical RUN_1/RUN_2 must not start until one exact candidate is durable and FINAL_SHA == REMOTE_SHA == LOCAL_SHA == BOUND_SHA for the reviewed bytes.

CURRENT_KNOWN_MECHANISM_EVIDENCE=
- Result -> Verify -> Reconcile -> NEXT_READY mechanism has been reported as source-grounded/proven on relevant bytes;
- zero-human A->B mechanism has been reported as source-grounded, but there is no accepted certified physical instance yet;
- restart/no-replay mechanism has source-grounded evidence, but executed physical proof is still required;
- process/resource bounding has source-grounded evidence;
- actual certifying RUN_1 and RUN_2 remain OPEN until exact candidate reconciliation and physical proof.

CURRENT_RELEASE_BLOCKER=
Exact candidate custody/publication/binding is inconsistent.
An orphan/local-only fixed commit is not a releasable candidate merely because its object exists locally.

NEXT=DISPATCHER_DECIDE_DFD22BB_PUBLISH_OR_RULE_OUT
NEXT_IF_PUBLISHED=SOLE_WINDOWS_WRITER_RECHECK_ONLY_REMAINING_CONFIRMED_BLOCKERS
NEXT_AFTER_WRITER=POST_WRITER_NEW_SHA_CONVERGENCE
NEXT_AFTER_CONVERGENCE=MAC_EXACT_BINDING
NEXT_AFTER_BINDING=SINGLE_PHYSICAL_OWNER_RUN1
NEXT_AFTER_RUN1_PASS=SINGLE_PHYSICAL_OWNER_RUN2
NEXT_AFTER_RUN2_PASS=CORE_FREEZE
NEXT_AFTER_CORE_FREEZE=MINIMUM_REAL_PILOT

MAX_SOURCE_WRITERS=1
MAX_PHYSICAL_MAC_OWNERS=1

READ_ONLY_WALL_STATE=TARGETED_RECONCILIATION_ONLY
READ_ONLY_WALL_RULE=
Do not reopen broad review. Only work a unique reconciliation, changed-byte, actual-evidence, or explicitly routed lane. All other windows park.

COST_GUARD:
- do not send Muse/Google back to old PRE_CODEX work;
- do not repeat local/remote runner discovery;
- do not repeat acceptance-harness false-proof finding;
- do not reopen Ledger absent RETEST_TRIGGER;
- do not invent new read-only shards merely to keep windows busy;
- do not use watch/sleep loops inside model turns;
- when no real work exists, emit NO_REAL_WORK and let an external supervisor wait without model tokens.

INVALIDATION_TRIGGER:
- dispatcher publishes/rules out the orphaned fixed commit;
- writer produces a new durable SHA;
- exact binding changes;
- actual RUN_1 evidence appears;
- actual RUN_2 evidence appears;
- a proven causal defect invalidates current evidence.

WORKER_RULE:
Read this file before acting.
If the exact candidate identity is unresolved, do not perform physical proof.
Source/runtime/git identity truth beats stale prose.
