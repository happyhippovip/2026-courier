# Opus 4.6 — Ledger Final Convergence Queue — 2026-09-28

Status: HIGH-VALUE / C4 / READ_ONLY
Purpose: finish the Extended Execution Ledger by converging existing Google/Muse evidence, not by repeating deterministic checks.

## Hard laws

- RESULT_REUSE_FIRST=YES
- NO_BROAD_REPO_SCAN=YES
- NO_DUPLICATE_REVIEW=YES
- NO_IDLE_ANALYSIS=YES
- UNKNOWN stays UNKNOWN
- no application-source edits
- no Codex invocation
- no physical RUN_1/RUN_2
- unchanged PRE_CODEX fingerprint is not work
- use GLEDGER-101..130 and G181..G280 durable results before raw source
- deterministic gaps route to Google/C0-C1, not Opus
- one live claim per OL task

## Canonical inputs

- ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md
- ops/ai/GOOGLE_WINDOWS_LEDGER_QUEUE_G181_G280_2026-09-27.md
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/COURIER_MASTER_CONTROL_PLANE_2026-09-27.md

Use durable result summaries/syntheses whenever available:
G190/G200/G210/G220/G230/G240/G250/G260/G270/G280 and GLEDGER-130.

## Tasks

### OL-01 — Ledger entity-chain semantic convergence
Converge GOAL -> CONTRACT -> TASK -> ATTEMPT -> CLAIM/LEASE -> DISPATCH -> EXECUTION -> RESULT -> VERIFY -> RECONCILE -> NEXT_READY.
Done: one unambiguous identity/ownership chain; list only unresolved semantic collisions.

### OL-02 — Result/replay equivalence boundary
Converge result identity, duplicate equivalence, changed status/worker/attempt/dispatch/artifact semantics, persistence/reload behavior.
Done: exact equivalence invariant and exact non-equivalent cases.

### OL-03 — Trusted-content authority boundary
Converge task-owned expected_sha256, worker-controlled fields, server-byte verification, artifact ambiguity/error semantics.
Done: trusted/untrusted field boundary with no authority inversion.

### OL-04 — Persistence/restart truth model
Converge atomic persistence, malformed/truncated state, accepted/pending/reconcile survival, restart checkpoints and stale-result behavior.
Done: minimal durable-state model needed to prevent loss or double effect.

### OL-05 — Reconcile/NEXT_READY motor semantics
Converge verify -> reconcile -> dependencies -> READY -> eligibility -> dispatch.
Done: deterministic transition invariant and only unresolved causal gaps.

### OL-06 — Claim/lease/harvester authority
Converge claim ownership, lease renewal/release, Harvester trust, contradiction handling and queue refresh ownership.
Done: one authority matrix with no self-upgrade path.

### OL-07 — Continuity semantics
Converge /clear, fresh session, provider/account/host change, stale cache rejection and do-not-repeat fingerprints.
Done: exact continuation contract across context boundaries.

### OL-08 — Cost/resource/provider Ledger semantics
Converge quota/cost/resource/device/wall fields without mixing provider availability with logical task identity.
Done: minimum truthful fields + stop/fallback semantics.

### OL-09 — Security/redaction/customer projection
Converge secret/redaction boundary and internal Ledger -> customer/owner projections.
Done: minimal safe projections; no secret/private-field leakage.

### OL-10 — Schema / implementation-packet consistency
Use GLEDGER-124..129 and relevant G syntheses only.
Done: identify contradictions between canonical Ledger contract, schema gap map, integration/server gap maps, tests and Central Writer packet.

### OL-11 — Ledger acceptance falsifiability
Review whether acceptance matrix can actually disprove bad Ledger behavior instead of only confirming happy paths.
Done: strongest missing negative cases, if any.

### OL-12 — Ledger finish criteria
Define exact evidence required for:
LEDGER_SPEC_READY
HARVESTER_READY
NEXT_READY_READY
CONTINUITY_READY
COST_GUARD_READY
SECURITY_BOUNDARY_READY
CUSTOMER_PROJECTION_READY
CENTRAL_WRITER_PACKET_READY

### OL-13 — Final Ledger convergence synthesis
Inputs: OL-01..12 + current durable Ledger syntheses only.
Output:
LEDGER_SPEC_READY=
RESULT_REPLAY_READY=
TRUST_BOUNDARY_READY=
PERSISTENCE_RESTART_READY=
MOTOR_READY=
CLAIM_HARVEST_READY=
CONTINUITY_READY=
COST_RESOURCE_READY=
SECURITY_PROJECTION_READY=
IMPLEMENTATION_PACKET_READY=
ACCEPTANCE_READY=
LEDGER_PREP_COMPLETE=
OPEN=
BLOCKED=
TOP_CAUSAL_BLOCKER=
NEXT_EXACT_ACTION=

## End

Do not invent OL-14.
If OL-13 closes Ledger preparation, stop Ledger convergence work.
