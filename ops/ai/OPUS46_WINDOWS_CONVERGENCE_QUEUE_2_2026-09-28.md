# Opus 4.6 Windows Convergence Queue 2 — 2026-09-28

Status: AUTHORIZED HIGH-VALUE SECOND QUEUE
Host: WINDOWS
Provider: OPUS_4_6
Purpose: second independent convergence layer after O46, focused on semantics, authority, failure containment, cost discipline, pilot readiness, and durable routing.

This queue is explicitly authorized by the operator.
It does NOT extend O46 with O46-13+. O46 remains closed on its own terms.

## Hard laws

- READ_ONLY_CONVERGENCE by default.
- No application-source edits.
- No Codex invocation.
- No physical RUN_1/RUN_2.
- No repeated PRE_CODEX validation for unchanged fingerprint.
- Use durable result summaries before raw source.
- Do not duplicate Google/Muse deterministic checks.
- UNKNOWN stays UNKNOWN.
- One live claim per task.
- Expensive-model admission must be justified.
- RESULT_REUSE_FIRST=YES.
- NO_BROAD_REPO_SCAN=YES.
- NO_DUPLICATE_REVIEW=YES.
- NO_BUSYWORK=YES.

Canonical inputs:
- ops/ai/COURIER_MASTER_CONTROL_PLANE_2026-09-27.md
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md
- ops/ai/GATE_STATE_CURRENT.md
- ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md
- ops/ai/WORKER_SELF_IDENTIFICATION_AND_ROUTING_CONTRACT_2026-09-28.md
- ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md

## Tasks

### O47-01 — Authority-boundary review
Review writer/runner/reviewer/harvester/preparer ownership boundaries.
Done: exact authority matrix + any path where a lower-authority worker could self-upgrade.

### O47-02 — Gate-state machine review
Review OPEN -> REPORTED -> DURABILITY_PENDING -> VALIDATING -> READY -> CONSUMED transitions.
Done: transition table + impossible/ambiguous states + smallest coordination fixes.

### O47-03 — Durable-truth precedence review
Review conflicts among repo pointer, local session cache, result summaries, gate state, queue generation, and explicit handoff.
Done: deterministic precedence order + TRUTH_CONFLICT conditions.

### O47-04 — Failure containment review
Review whether one failed/contradicted task can contaminate later PASS, READY, queue generation, or physical proof.
Done: containment invariants + only real propagation gaps.

### O47-05 — Retry/retest semantics review
Review RETEST_TRIGGER, retry, replay, rerun, fresh attempt, fresh dispatch, and stale evidence invalidation.
Done: exact semantic separation + ambiguity list.

### O47-06 — Cost-admission review
Review whether provider/model/window admission follows cheapest sufficient capability and avoids duplicated expensive reasoning.
Done: cost leak map + exact admission constraints.

### O47-07 — Model-routing correctness review
Review C0..C5 routing, reasoning-level selection, host placement, and wrong-fit handoff behavior.
Done: routing matrix + misroutes + conservative unknown-model policy.

### O47-08 — Queue-generation integrity review
Review generation fingerprints, supersession, completed-task carryover, and prevention of accidental task resurrection.
Done: generation invariants + any replay/resurrection risk.

### O47-09 — Claim/lease fairness and starvation review
Review claim ownership, stale thresholds, lease renewal, release, synthesis starvation, and queue fairness.
Done: only material starvation/deadlock/livelock risks.

### O47-10 — Harvester trust-boundary review
Review what a Harvester may trust from worker results versus what requires independent durable evidence.
Done: trusted/untrusted field matrix + overwrite/contradiction rules.

### O47-11 — Physical-proof falsifiability review
Review whether RUN_1/RUN_2 evidence design can actually falsify the core claims instead of merely collecting confirming logs.
Done: falsification conditions + missing negative evidence.

### O47-12 — Core-Freeze decision semantics
Review exact conditions under which Core may be FROZEN, reopened, or partially invalidated.
Done: freeze/unfreeze/revalidation rules bound to evidence fingerprints.

### O47-13 — Pilot measurement integrity
Review HIPG, RSR, NDR, setup time, support effort, provider cost, and payment signal for measurement ambiguity/gaming.
Done: minimum honest measurement contract.

### O47-14 — Security/privacy minimum review
Review only current pilot/core data-flow boundaries, secret handling, repo visibility, retention/deletion assumptions, and least-privilege needs.
Done: minimum blocking security/privacy gaps; no enterprise overbuild.

### O47-15 — Product-promise evidence review
Review whether current proof plan actually supports the promise: user starts once, returns later, sees trustworthy continuation/state/next action.
Done: promise -> evidence mapping + uncovered promise claims.

### O47-16 — Second Opus synthesis
Inputs: O47-01..O47-15 results only.
Done: compact convergence handoff:
AUTHORITY=
GATE_MACHINE=
TRUTH_PRECEDENCE=
FAILURE_CONTAINMENT=
RETRY_SEMANTICS=
COST_ADMISSION=
MODEL_ROUTING=
QUEUE_INTEGRITY=
CLAIM_LEASE=
HARVESTER_TRUST=
PHYSICAL_FALSIFIABILITY=
CORE_FREEZE=
PILOT_METRICS=
SECURITY_PRIVACY=
PRODUCT_PROMISE=
TOP_CAUSAL_BLOCKER=
NEXT_EXACT_ACTION=

## End condition

When O47-01..O47-16 are complete or explicitly blocked:
- do not invent O47-17;
- persist O47-16;
- if no new invalidation trigger exists, TRUE_IDLE.
