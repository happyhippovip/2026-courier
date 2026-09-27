# Muse — Ledger Adversarial Finish Queue — 2026-09-28

Status: C2 INDEPENDENT QA / READ_ONLY
Purpose: falsify Ledger assumptions and close QA gaps without repeating Google deterministic work or Opus convergence.

## Hard laws

- RESULT_REUSE_FIRST=YES
- NO_BROAD_REPO_SCAN=YES
- NO_DUPLICATE_REVIEW=YES
- no application-source edits
- no physical RUN_1/RUN_2
- no PRE_CODEX revalidation
- UNKNOWN stays UNKNOWN
- use durable Google/Opus Ledger results first
- one live claim per ML task

## Tasks

### ML-01 — Identity-chain falsification
Try to find any ambiguity where Goal/Task/Attempt/Execution/Result/Verification/Reconciliation identities could be confused or silently rebound.

### ML-02 — Replay negative-case QA
Review identical replay vs changed status/worker/attempt/dispatch/artifact cases and persistence/reload boundary.
Done: any false duplicate-ACK path identified.

### ML-03 — Trusted-content inversion QA
Try to find any path where worker-supplied expected hash/metadata could influence trusted verification authority.

### ML-04 — Persistence corruption/restart QA
Review malformed/truncated/partial/pending/reconcile persistence scenarios for fail-open behavior or duplicate effects.

### ML-05 — Reconcile idempotence QA
Review repeated verify/reconcile/dependency update paths for double effect or premature NEXT_READY.

### ML-06 — Claim/lease concurrency QA
Review claim atomicity, stale thresholds, renewal/release ownership and double-owner edge cases.

### ML-07 — Harvester contradiction QA
Review whether malformed, stale, duplicate or contradictory returned results can overwrite durable truth.

### ML-08 — Continuity falsification
Try to break /clear/session/provider/account/host continuity using stale local cache, missing checkpoint or wrong precedence.

### ML-09 — Security/redaction QA
Review Ledger/result/projection fields for secret/private-data leakage or unsafe provenance assumptions.

### ML-10 — Acceptance-matrix adversarial QA
Review existing Ledger acceptance tests for missing negative/failure cases. Do not run broad suites.

### ML-11 — Implementation-packet QA
Review Central Writer packet against canonical Ledger contract and result syntheses; flag only material omissions/contradictions.

### ML-12 — Ledger finish-gate independent QA
Independently assess GLEDGER-130 / OL-13 fields from durable evidence.
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
TOP_FALSE_GREEN_RISK=
NEXT_EXACT_ACTION=

## End

Do not invent ML-13.
When ML-12 is complete and no RETEST_TRIGGER changed:
MUSE_LEDGER_QA_COMPLETE=YES.
