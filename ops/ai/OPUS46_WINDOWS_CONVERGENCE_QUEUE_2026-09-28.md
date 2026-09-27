# Opus 4.6 Windows Convergence Queue — 2026-09-28

Status: HIGH-VALUE / EXPENSIVE-MODEL / READ-ONLY
Host: WINDOWS
Provider: OPUS_4_6
Purpose: independent convergence review after Google/Muse wall work without duplicating deterministic checks.

## Hard laws

- Do not edit application source.
- Do not invoke Codex.
- Do not execute RUN_1/RUN_2.
- Do not revalidate an unchanged PRE_CODEX fingerprint.
- Read ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md and ops/ai/GATE_STATE_CURRENT.md first.
- RESULT_REUSE_FIRST=YES.
- NO_BROAD_REPO_SCAN=YES.
- NO_DUPLICATE_REVIEW=YES.
- One live claim per task.
- New window/session/account does not reset completion.
- Prefer durable result summaries over raw source.
- If evidence is absent, say UNKNOWN/OPEN; never invent PASS.
- This is not a 100x queue. Admit only a small number of Opus workers.

## Inputs

Canonical:
- ops/ai/COURIER_MASTER_CONTROL_PLANE_2026-09-27.md
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md
- ops/ai/GATE_STATE_CURRENT.md
- ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md

Use referenced durable result summaries only as needed.

## Tasks

### O46-01 — Canonical truth convergence
Compare current durable truth files and result summaries for contradictions in phase, ownership, FINAL_SHA state, gate state, and next action.
Done: compact contradiction list with earliest causal inconsistency only.

### O46-02 — Cost-safety architecture review
Review whether gate/result reuse, admission control, idle behavior, and one-owner validation actually prevent repeated paid work.
Done: concrete remaining cost-leak list and smallest coordination fix.

### O46-03 — Ledger invariants convergence
Synthesize whether Goal/Task/Attempt/Execution/Result/Verification/Reconciliation identities and provenance form one coherent trustworthy ledger model.
Done: invariant map + only unresolved semantic gaps.

### O46-04 — Replay/trusted-content convergence
Synthesize replay/idempotency and expected_sha256 trust-boundary evidence from completed Google/Muse results.
Done: exact invariant set + contradictions/UNKNOWNs, no retest unless evidence invalidated.

### O46-05 — Motor/autonomy convergence
Review Result -> Verify -> Reconcile -> NEXT_READY -> Eligibility -> Dispatch semantics and whether the system can honestly support the claimed autonomy surface.
Done: causal chain map + blocking UNKNOWNs only.

### O46-06 — RUN_1 proof-design review
Review prepared RUN_1 evidence capture plan for whether it can decisively prove A once, verify/reconcile, B auto-start, zero human relay, and no FAILED execution.
Done: missing-proof-field list only; do not execute run.

### O46-07 — RUN_2/restart proof-design review
Review restart/no-replay evidence plan for whether it can decisively prove persisted A, restart, no A re-execution, reconcile, B auto-start, A count=1.
Done: missing-proof-field list only.

### O46-08 — Core Freeze convergence
Review Proof Cards, fingerprints, restart matrix, resource bounds, no-tight-polling, Trusted Ledger and Reliable Motor evidence.
Done: PROVEN/OPEN/BLOCKED/UNKNOWN matrix with no speculative work.

### O46-09 — Cross-host continuity review
Review Windows -> Mac -> provider/session continuity and exact durable state needed so work does not reset or duplicate across hosts.
Done: only real portability gaps with causal impact.

### O46-10 — Human-relay/autonomy semantics
Review HUMAN_RELAY_COUNT, HUMAN_REQUIRED, A0-A4, and operator-return rules for ambiguity that could create false autonomy claims.
Done: exact semantic clarifications needed, if any.

### O46-11 — Minimal pilot convergence
Review whether current minimum pilot plan tests the core promise without premature Product Shell/expansion.
Done: smallest pilot evidence package and missing preconditions; no marketing expansion.

### O46-12 — Final Opus convergence handoff
Inputs: O46-01..O46-11 results only.
Done: one compact handoff:
CANONICAL_TRUTH=
GATE_STATE=
COST_SAFETY=
LEDGER=
REPLAY_TRUST=
MOTOR=
RUN1_PREP=
RUN2_PREP=
CORE_FREEZE=
CONTINUITY=
AUTONOMY=
PILOT=
TOP_CAUSAL_BLOCKER=
NEXT_EXACT_ACTION=

## End condition

When all tasks are complete/blocked:
- do not invent O46-13;
- persist O46-12;
- if no new invalidation trigger exists, TRUE_IDLE.
