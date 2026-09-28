# GLEDGER-109 Result — Verification Record

TASK_ID=GLEDGER-109
STATUS=PROVEN (by reused harvested evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=L3 (verify endpoint rules, independence, resend ACK); GLEDGER-108 (evidence refs consumed); GLEDGER-102 (RESULT_STATES, no-evidence rule); PHYS-002 (live PASS observed: VERIFIER-CANARY-01 re-hash → RECONCILED)

## Canonical verification record
REQUIRED: `task_id`, `result_id` (must equal the result under verification — mismatch → 400/409), `verifier_id` (independent identity, MUST differ from result `worker_id`; self-certification → 400), `verdict` ∈ {PASS, FAIL} only (no third value; malformed verdict → 400), `artifacts` (must equal the result's artifacts — inequality → 400), `timestamp`/binding (server-recorded accept time).
OPTIONAL: verifier notes/detail strings (informational; never substitute for checked evidence).
FORBIDDEN: PASS with unchecked or partially-checked evidence; verifier == worker; verdict inference from silence; PASS on legacy path where exact-content was required (GLEDGER-103 acceptance: missing task expectation → legacy only).

## Checked-evidence rule (normative — the done condition)
A PASS is valid IFF the verifier independently re-hashed server-held bytes and re-checked every binding (sha/size/name/artifact_id + BINDING_FIELDS vs task) and, where the task carries expected_sha256, the pin. The record's validity is the conjunction of checks, not the verdict string: a PASS verdict with any unchecked element is VOID (treated as no-verification; task stays RESULT_RECEIVED). No evidence → no PASS, no exceptions, no legacy upgrade.

## Verifier independence (normative)
Independence is identity + path: different worker_id AND independent fetch of server bytes (never worker-supplied bytes). The verify resubmission of an identical verification on an already-RECONCILED task → ACK_DUPLICATE (test-anchored); different result_id on RECONCILED → 409.

MISSING=None for the record definition.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-110 (reconcile consumes verification records); GLEDGER-115 (contradictory verdicts procedure).
DO_NOT_REPEAT_FINGERPRINT=gledger-109-verification-record-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-53c9cbc7e1f59e0f

DO_NOT_REPEAT_FINGERPRINT=sha256-9638965c02a7188e

DO_NOT_REPEAT_FINGERPRINT=sha256-a453295a0ab66356
