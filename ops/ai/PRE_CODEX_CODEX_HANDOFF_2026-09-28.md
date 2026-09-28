# PRE_CODEX → CODEX HANDOFF — 2026-09-28 (durability owner)

## Binding
- FINAL_SHA=`34b0a4264bf763bc2a78f761ffba36e47706b2cf` ("fix(core): apply Q027 Central Writer fix packet with updated test")
- BASE_SHA=`4c1e24ccc522042af826bc4c2b595daf85d097f9` (ancestor, verified via merge-base)
- REMOTE: `origin/candidate-b-1` == FINAL_SHA (canonical path, MAC_EXACT_BINDING
  Step 2) + mirror `origin/evidence/pre-codex-final-34b0a42` == FINAL_SHA
- AUTHORITATIVE_READY=YES (see `ops/ai/GATE_STATE_CURRENT.md`)

## Exact source scope (base→SHA, verified via git diff --name-only)
- `scripts/courier_verifier.py` (task-owned expected hash, upload-based verify)
- `scripts/integration_contract.py` (worker `expected_sha256` rejected at intake)
- `server/app.py`
- `tests/test_artifact_upload_flow.py`
- `tests/test_p3_server_idempotency.py` — authorized, unmodified (compliant)
- Plus 18 `ops/ai/*` coordination files (pre-existing V2 publish commits, no source impact)

## Executed evidence on exact SHA bytes (export `/tmp/precodex-34b0a42` via git archive)
- `py_compile` clean on all 8 scope+runner files
- `PYTHONPATH=. pytest tests/test_artifact_upload_flow.py
  tests/test_p3_server_idempotency.py tests/test_result_identity_binding.py
  tests/test_integration_contract.py` → **44 passed, 0 skipped (7.4s)**
- `git diff --check` clean on `scripts/ server/ tests/ schemas/` (docs-only noise elsewhere)
- Reused (not re-run): PRE_CODEX_GATE Q021–Q026 evidence (44/44 at pre-packet HEAD
  817c7979 — superseded by the executed run above for the packet files)

## Known residuals (non-blocking, tracked by INVALIDATION_TRIGGER)
- Unpublished local writer drift past SHA (`09166bd5..e11749b6`, detached HEAD,
  dirty tree): NOT part of FINAL_SHA; any future branch advance re-arms the gate.
- Stale `09166bd5` "actual integration SHA" note in
  `WINDOWS_CENTRAL_WRITER_FINAL_COMMIT_2026-09-28.md`: superseded by the canonical
  act of pointing `candidate-b-1` at `34b0a42`.
- RUN_1/RUN_2: NOT executed (outside durability lane) — designated executor only.

## For Codex
Bind Mac verification to FINAL_SHA per `MAC_EXACT_BINDING_SPECIFICATION_2026-09-28.md`
Steps 2–5 (tip check, scope check, whitespace check, targeted tests, attestation).
Fetch: `git fetch origin candidate-b-1 evidence/pre-codex-final-34b0a42`.
Invalidate and return to gate owner if: REPORTED_FINAL_SHA changes, refs move,
or any check above fails on fresh fetch.

DO_NOT_REPEAT_FINGERPRINT=sha256-precodex-codex-handoff-34b0a42-01
