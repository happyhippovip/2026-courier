# Ledger software gate — bounded delta review

HEAD: d5cd013033156657630ccaa7f8017ab1f842c686
Fetched origin/release-candidate-integration: 4cf6fad76c5835474ca54486b0e520aea6cdc993
Production owner: GOOGLE. No production changes by Codex.
Decision: NOT ACCEPTED; active working-tree mutation prevents a stable final binding.

## Fingerprint comparison

The four non-server fingerprints in CODEX_TRUST_ROOT_DELTA_CHECKPOINT.md
remain unchanged (Ledger, attestation resolver, receipt contract, receipt tests).
server/app.py changed from 3132430de32d46cc0b4a56f8e28b9b52283357aa92e92999f55c65a6e44ad963
to ff69613edf09c810f41a7c88bef9ca52e65a9d96b8af50eff82da169b9246247
at inspection, then b555d6db1e3ea5d5679f316b9f57e544fe04422da057a6db43ce1c77b04eca58
after the targeted test. No stable SHA-only acceptance is possible for these dirty bytes.
The previous server bytes were not retained, so git diff against HEAD is not an
exact diff against the last reviewed working-tree hash.

## Gate decisions

| Gate | Verdict | Exact evidence and limit |
|---|---|---|
| Trust Root | REPRODUCIBLE_DEFECT | Unchanged Ledger hash retains the environment bypass reproduced in CODEX_TRUST_ROOT_ENV_BYPASS.md. Reused rejection; no repeat test. |
| Receipt provenance | MISSING_EVIDENCE | New verify endpoint requires received_runtime_identity, compared with task.server_binding. Existing genuine receipt test sends no such field and now gets HTTP 400 before receipt creation. Client/contract migration and stable implementation evidence required. |
| Freshness | MISSING_EVIDENCE | Prior local freshness tests are historical component evidence. End-to-end receipt consumption remains blocked; no current integrated acceptance. |
| Replay | MISSING_EVIDENCE | Runtime/revocation/replay combinations cannot be accepted through the blocked positive receipt path. |
| Idempotency | MISSING_EVIDENCE | Prior Ledger duplicate contract remains historical passing evidence. Updated server receipt idempotency test stops on first verification; new server boundary is unaccepted. |
| False-Green | REPRODUCIBLE_DEFECT | Unchanged attestation bypass invalidates global acceptance despite earlier passing narrow false-green tests. |
| Ledger-last | MISSING_EVIDENCE | Genuine authenticated receipt cannot currently traverse tested producer/verification/Guard/Ledger path. Prior schema mismatch for result_sha256 remains in unchanged Ledger bytes. |

## New targeted executable evidence

Command:
`python3 -m pytest -q --tb=short tests/test_ledger_authenticated_receipts.py::test_independent_authenticated_receipt_and_idempotency`

Observed: 1 failed in 0.73s; tests/test_ledger_authenticated_receipts.py:67,
HTTP 400 instead of HTTP 200 at /tasks/verify. Inspection shows the new
received_runtime_identity requirement. This is a contract incompatibility with
the existing acceptance caller, not proof that missing runtime identity should
be accepted. Production caller compatibility remains unproven.

## Requested combined attacks

- Valid receipt + wrong runtime: MISSING_EVIDENCE at integrated boundary.
- Revoked verifier + identical replay: MISSING_EVIDENCE at integrated boundary.
- New URL + old digest: MISSING_EVIDENCE; Ledger receipt schema blocks positive setup.
- Revision conflict during evidence consumption: MISSING_EVIDENCE for trusted consumption.
- Restart between receipt persistence and Ledger update: MISSING_EVIDENCE for integrated path.

No unchanged suites rerun. No physical proof claimed. No evidence of absence
of defects inferred from test names or blocked test setup.

## Exact next owner action

GOOGLE: finish a stable Trust Root repair packet, first removing the existing
PYTEST_CURRENT_TEST bypass. Reconcile authenticated receipt schema and verify
caller runtime-binding contract, retaining fail-closed behavior. Include the
genuine positive receipt test plus mismatch/revocation/replay tests and exact
file fingerprints. Codex then reviews only those changed boundaries.

No repeated tests or polling while the owner is editing. STATE=IDLE_PENDING_STABLE_GOOGLE_DELTA.
