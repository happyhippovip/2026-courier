# Exact Mac Binding Specification — 2026-09-28

**Role**: `COURIER_EXACT_MAC_BINDING_PREPARER`  
**Host**: MAC (`/Users/user/Downloads/2026-courier`)  
**Provider**: GOOGLE_CLI_OR_MUSE  
**Mode**: PRE_PHYSICAL_PREP  
**Date**: 2026-09-28 00:16:00+02:00  
**Status**: BINDING_PREPARED (READY FOR PHYSICAL RUN GATE)  

---

## 1. Exact Mac Binding Matrix

```yaml
FINAL_SHA: 34b0a4264bf763bc2a78f761ffba36e47706b2cf
LOCAL_SOURCE_SHA: 34b0a4264bf763bc2a78f761ffba36e47706b2cf
EXPECTED_SOURCE_SHA: 34b0a4264bf763bc2a78f761ffba36e47706b2cf
TREE_SHA: bc9c45e9c8079c10366843b9fc3baf06e450b5f2
COMBINED_SOURCE_FINGERPRINT: 1d8a46565a46abb4eef4f7fdbde0f2e60a40e67f4561ddaae5603d9e5b3989cd
BUILD_ID: Darwin-24.3.0-x86_64-py3.9.13-b34b0a426
RUNTIME_ID: Darwin-24.3.0-x86_64-py3.9.13
CONFIG_FINGERPRINT: 8b9d8fdc746f8f4c3cb400477e2aeda0e99412c8204ac1ddc06563d82b603b17
PYTHON_ENV: /usr/local/bin/python3 (Python 3.9.13, /Library/Frameworks/Python.framework/Versions/3.9)
SERVER_COMMAND: COURIER_STATE_DIR=/Users/user/courier_work/canary_run1/state COURIER_ARTIFACTS_DIR=/Users/user/courier_work/canary_run1/artifact-store PORT=8081 /usr/local/bin/python3 server/app.py
WORKER_COMMAND: COURIER_SERVER=http://127.0.0.1:8081 COURIER_WORKER_HOME=/Users/user/courier_work/canary_run1/worker /usr/local/bin/python3 scripts/mac_worker/daemon.py
VERIFIER_COMMAND: COURIER_SERVER=http://127.0.0.1:8081 COURIER_VERIFIER_API_KEY=verifier-test-key-34b0a426 /usr/local/bin/python3 scripts/courier_verifier.py
PORT_PLAN: Port 8081 (staging coordinator isolated from production Port 8080 PID 69407)
STATE_DIR: /Users/user/courier_work/canary_run1/state
ARTIFACT_DIR: /Users/user/courier_work/canary_run1/artifact-store
LOG_DIR: /Users/user/courier_work/canary_run1/logs
RUN1_WORKSPACE: /Users/user/courier_work/canary_run1
RUN2_WORKSPACE: /Users/user/courier_work/canary_run2
KEY_SEPARATION_READY: YES
PROCESS_ISOLATION_READY: YES
```

---

## 2. Component File Hashes (`FINAL_SHA: 34b0a426`)

- `scripts/courier_verifier.py`: `2fbffc4e42895a357f59dfa2fca36d6ad48236ed295283c3f558b7061d304e20`
- `scripts/integration_contract.py`: `aeb3ab6323711d393640b9849274ac174d451b36a9d474d603ded2e55cfcee9d`
- `server/app.py`: `cd57c7303092f5d50ad41a4e5afa01e6ec1a1cf37641d4d410c30b6a5b96a541`
- `tests/test_artifact_upload_flow.py`: `3d9042359570d12260f85258d7222b2351361b1b8ad477b198d10129ba49f1d4`
- `tests/test_p3_server_idempotency.py`: `084464f3709b482a23484ba4bfaf5943a3db8734757ed609df31be36a4ece002`
- `tests/test_result_identity_binding.py`: `0a52a680adb0fa6f8c52e841d245db0e29d9d444817f0ecc6fb9004f2f4ef525`
- `tests/test_integration_contract.py`: `012bf83a400e91cc351edcd8c11bd80dbebab80cd38274cbbeca1b7c36af663e`

---

## 3. Preparation Gaps & Status

- **Compilation / Syntax Gate**: `PY_COMPILE=PASS` (0 errors across all 7 candidate files).
- **Targeted Unit Tests**: 44/44 PASS in 7.33s (`SKIPPED=0`).
- **Whitespace / Diff Check**: 0 errors on application files (`scripts/`, `server/`, `tests/`).
- **Key Separation**: Enforced via separate bearer tokens:
  - Worker: `COURIER_WORKER_API_KEY` (allows task claim, result submission, byte upload).
  - Verifier: `COURIER_VERIFIER_API_KEY` (allows task verification poll, raw byte download, verification post).
  - Disallowed cross-actions return HTTP 401/403.
- **Process Isolation**: Enforced via supervisor `MAX_HEAVY_JOBS=1`, separate state directories, independent port binding (Port 8081), and distinct process groups.
- **Physical Execution Gate**: `READY_FOR_PHYSICAL_RUN=PENDING_EXTERNAL_GATE` (Physical RUN_1/RUN_2 will execute upon authorization).
