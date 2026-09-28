# M183 — Candidate Source Scope Checksum Binding

## 1. Overview & Authority
- **Task ID**: M183
- **Area**: SOURCE_BINDING
- **Status**: COMPLETE

## 2. Invariant Scope Files
The five canonical source files are bound:
1. `scripts/courier_verifier.py`
2. `scripts/integration_contract.py`
3. `tests/test_artifact_upload_flow.py`
4. `server/app.py`
5. `tests/test_p3_server_idempotency.py`

Checksum validation ensures that no local unstaged or rogue modifications alter candidate behavior during proof preparation.
