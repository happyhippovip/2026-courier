# GLEDGER-108 Result — Artifact Evidence Refs + Trusted Expectation Placement

TASK_ID=GLEDGER-108
STATUS=PROVEN with one carried open (OPEN below; queued to writer, not re-litigated)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=P4 hash-chain trace (upload/put/check_reference/verify_uploaded_artifact, artifact_id derivation, name safety); POST200-021 cases 1–7; PHYS-002 (upload→hash→verify observed live)

## Artifact evidence ref (normative)
Fields: `path` (task-relative name, dual-platform safe), `sha256` (server-computed at upload, cross-checked against worker claim), `artifact_id` (deterministic: sha256 over binding fields + name + content hash — dispatch-scoped, write-once), `size` (byte-exact, 16MB cap enforced at upload), optional `expected_sha256` (pin, see placement).
Chain (each link enforced, in order): task-name allowlist at upload → server hashes bytes itself (worker hash never trusted alone) → claimed sha/size cross-check → content-addressed atomic blob write + write-once record (conflict + corrupt-blob detection) → `check_reference` at result-submit (record binding + name/sha/size vs record) → independent verifier re-hash of server bytes + full binding recheck at verify.

## Trusted expectation placement (normative — the done condition)
Task-owned expectations live ONLY in the task template (`artifacts` entries: names, or {path, expected_sha256} dicts) and in server-held upload records. Worker input (result refs, claimed hashes) is EVIDENCE CANDIDATE material: it is checked against the two trusted sources, never promoted to expectation. Concretely: a worker-supplied `expected_sha256` that mismatches server bytes → FAIL; worker omission → legacy record-binding path still enforced (no bypass); missing task expectation → legacy only, never exact-content PASS.
OPEN (ownership binding): on b1 nothing compares a result ref's `expected_sha256` against the TASK template's value — the pin is verified against server bytes only. Canonical rule (worker input cannot become trusted expectation) is satisfied in effect (bytes are server-held) but the task→pin comparison has no code anchor. Writer ruling queued (POST200-021 cases 1/4). Canonical Ledger records the comparison as REQUIRED regardless of b1's current coverage.

## Forbidden
Server trusting worker-claimed sha without re-hash; artifact_id reuse across dispatches; path traversal (absolute/drive/UNC/.., enforced both platforms); blobs addressable outside content-hash; verification against worker-held bytes.

MISSING=None for placement definition. OPEN item is writer-owned.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-109 (verification record consumes evidence refs + expectation placement); GLEDGER-129 (writer packet item if ruling requires code).
DO_NOT_REPEAT_FINGERPRINT=gledger-108-artifact-evidence-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-8fbffa392219e6c6

DO_NOT_REPEAT_FINGERPRINT=sha256-a21a613e00d5abee

DO_NOT_REPEAT_FINGERPRINT=sha256-1f54c1479a58ef34
