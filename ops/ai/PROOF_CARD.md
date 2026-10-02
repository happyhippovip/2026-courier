# Core Freeze Proof Card (Assembly)

## Goal/Contract Refs
- 12-Case Ledger Requirements (Identity, Persistence, Verifiability, Reconcile, Autonomy).
- Zero-human relay requirement post-start (`HUMAN_RELAY_COUNT=0`).

## Task Identity
- **FINAL_SHA**: `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4`
- **BASE_SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9`
- **Scope**: `server/app.py`, `scripts/integration_contract.py`, `scripts/courier_verifier.py`, `tests/test_artifact_upload_flow.py`, `tests/test_p3_server_idempotency.py`.

## Actual Result
- **Pre-Codex Status**: `GREEN` (57 targeted assertions passed, 1 skipped darwin-only, 0 failed).
- **Physical Mac Run**: `[PENDING_DISPATCH]`

## Acceptance Criteria
- Exactly one execution of Task A.
- Expected hash matches server bytes perfectly.
- A->B autonomous progression observed in isolated environment.
- Restart proves persistence and no Task A replay.

## Evidence IDs
- `PRE_CODEX_HANDOFF.result.md`
- `EVIDENCE_FINGERPRINT_REPORT.md`
- `SCOPE_CHECK_EVIDENCE.md`
- `RUN_PREP_AND_CORE_FREEZE_PACK.md`
- `PILOT_READINESS_DECLARATION.md`
- *Physical run evidence IDs pending Mac runner.*

## Proof Level
- **Current**: `SYNTHETIC_PRE_CODEX` (100% Green Local Verification)
- **Target**: `PHYSICAL_MAC_RUN`

## Covered Surface
- Server `ACK_DUPLICATE` logic with canonical artifact list/dict ordering.
- Verifier independent byte hashing & `expected_sha256` strictness.
- Integration Contract identity chain binding.
- Re-dispatch isolation & state mutation locks.

## Source Fingerprints
- `server/app.py`: `a0356d4bd380aed289974714bdb4ae98aa6b0a9a68b41f56a49a5ab3b04b64f8`
- `scripts/integration_contract.py`: `5bf969957cdd9d6c29fbeeb86c5e71969b119ed35b519c44ae4724463d48c287`
- `scripts/courier_verifier.py`: `17de06ccdec9b5bedc1cc14286b50f13e8e3505174383f3e79cf25778e5b4eb5`
- `tests/test_artifact_upload_flow.py`: `6ad67424eb27132e46839ab9ae4274135a0e37e8f9af3a76b379de0467878569`
- `tests/test_p3_server_idempotency.py`: `ca7556baf528221054e17508b4b4f85a3cf654c17904b027ce870e54d6572750`

## Human Interventions
- **Pre-Codex / Candidate Fixes**: Fully automated by AI agents.
- **Run Phase Target**: 0 (`HUMAN_RELAY_COUNT=0`).

## Revalidation Status
- Revalidation restricted strictly to changes in fingerprint or `FINAL_SHA`. Currently `VALID`.

## Restart & Resource Evidence Slots
- **Restart Log Slot**: `logs/server_run2.log`
- **Resource Constraints**: Port 8080 free, single heavy job ceiling (`MAX_HEAVY_JOBS=1`).
