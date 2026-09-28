# Family 18: Central Writer Compressed Action Packet

**Target Host**: WINDOWS CENTRAL WRITER  
**Allowed Files**: 5 Files Maximum (`scripts/courier_verifier.py`, `scripts/integration_contract.py`, `tests/test_artifact_upload_flow.py`, `server/app.py`, `tests/test_p3_server_idempotency.py`)

---

### Defect 1: Worker-Supplied Hash Authority
- **FILE**: `scripts/courier_verifier.py`
- **FUNCTION**: `verify_artifacts(task, result, fetch=fetch_artifact, local_verify=None)`
- **DEFECT**: Line 78 reads `art["expected_sha256"]` directly from the worker-supplied result dictionary, allowing worker hash injection.
- **REQUIRED_BEHAVIOR**: Derive `expected_sha256` strictly from `task["expected_artifacts"]` or `task["expected_sha256"]`. Ignore worker-supplied `expected_sha256`.
- **TARGETED_TEST**: `tests/test_artifact_upload_flow.py::test_verifier_checks_expected_sha256`
- **EVIDENCE**: `ops/ai/wall_results/POST200-021_result.md` (Case 1 & 4)
- **DO_NOT_CHANGE**: Server store copy fetching, independent re-hashing, remote worker upload enforcement.

### Defect 2: Worker Schema Injection
- **FILE**: `scripts/integration_contract.py`
- **FUNCTION**: `validate_durable_result(task, result)`
- **DEFECT**: Line 156 allows `"expected_sha256"` in `result["artifacts"]` schema.
- **REQUIRED_BEHAVIOR**: Disallow `"expected_sha256"` in `result["artifacts"]`. Allowed keys: `{"path", "sha256"}` or `{"path", "sha256", "artifact_id", "size"}`.
- **TARGETED_TEST**: `tests/test_integration_contract.py::test_verified_result_binds_identity_and_artifact`
- **EVIDENCE**: `scripts/integration_contract.py:156`
- **DO_NOT_CHANGE**: Core identity bindings (`goal_id`, `task_id`, `attempt_id`, `dispatch_id`, `worker_id`).

### Defect 3: Incomplete Duplicate ACK Match
- **FILE**: `server/app.py`
- **FUNCTION**: `task_result()`
- **DEFECT**: Line 367 compares only `("dispatch_id", "result_id", "status")`, omitting `worker_id` and `attempt_id`.
- **REQUIRED_BEHAVIOR**: Compare `("dispatch_id", "result_id", "status", "worker_id", "attempt_id")` and artifact list identity before issuing `ACK_DUPLICATE`.
- **TARGETED_TEST**: `tests/test_p3_server_idempotency.py::test_resent_result_is_acknowledged_idempotently`
- **EVIDENCE**: `server/app.py:367`
- **DO_NOT_CHANGE**: State serialization mutex, HTTP 409 Conflict rejection for conflicting results.

### Defect 4: Trailing Whitespace
- **FILES**: `scripts/courier_verifier.py`, `tests/test_artifact_upload_flow.py`
- **REQUIRED_BEHAVIOR**: Clean trailing whitespace to satisfy `git diff --check`.
