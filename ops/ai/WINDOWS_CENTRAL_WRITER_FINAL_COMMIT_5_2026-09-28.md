# Windows Central Writer - Fifth Batch of 3 Substeps

Continuing the execution protocol, we completed another 3 concrete substeps directly in the `2026-courier` repo as the authorized Windows Worker.

### 1. Resume Task Instruction Override Validation (Bug Fix & Test)
- **Problem**: In `server/app.py` `resume_task`, if an `instruction_override` was provided in the JSON payload, it was assigned directly to `step["instruction"]` without any type validation. A malicious or malformed payload (e.g. nested dict or list) would crash the Windows Worker's PowerShell Base64-encoding logic down the line.
- **Fix**: Added explicit `isinstance(data["instruction_override"], str) and data["instruction_override"].strip()` validation in `server/app.py`.
- **Evidence**: Added and passed `test_resume_task_rejects_invalid_instruction_override` in `tests/test_p3_server_idempotency.py`.

### 2. Missing Tests for Windows Artifact Path Safety (Test Completion)
- **Problem**: The Windows worker daemon relies on `is_safe_artifact_path` to prevent path traversal and UNC path injection (`C:`, `\`, `..\`, etc.) during artifact evidence collection. This crucial security function was entirely untested in the Windows test suite.
- **Fix**: Added comprehensive unit tests for `is_safe_artifact_path`.
- **Evidence**: Added and passed `test_is_safe_artifact_path` in `tests/test_windows_worker_contract.py`.

### 3. Missing Tests for Windows Artifact Upload Flow (Test Completion)
- **Problem**: The Windows worker `upload_artifact` function, which performs the actual HTTP POST of `X-Courier-Artifact` headers and raw byte streaming, had zero test coverage.
- **Fix**: Implemented a mocked `urllib.request.urlopen` test suite to verify the outbound HTTP request shape, header encoding, payload size validation, and SHA256 integrity verification inside `upload_artifact`.
- **Evidence**: Added and passed `test_upload_artifact_success` in `tests/test_windows_worker_contract.py`.

---
Commit SHA: (Pending commit)
All tests (`pytest tests/`) are 100% passing across the suite.
