# Candidate B-2 Cross-Platform Verification & Pilot Readiness Card

- **DATE**: 2026-09-26 18:35 CET
- **HOST_MAC**: `Darwin 25.6.0 x86_64` (MacBook-Pro-von-user.local)
- **HOST_WIN**: Windows Reference (`courier_canary_test-win-002.txt`)
- **CANDIDATE_SHA**: `83940de3d7d33776a712e7506aa76726d16f8587` (`origin/candidate-b-2`)
- **BASE_SHA**: `e7d047d9771bc8f0dd7d1f296983dd8171940b7d`
- **SINGLE_WRITER_HEAD**: Windows Google Writer (`google-windows@local.internal`)
- **EVIDENCE_BRANCH_MAC**: `evidence/google-mac-20260926`
- **EVIDENCE_BRANCH_WIN**: `evidence/google-windows-20260926`

---

## 1. Cross-Platform Verification Matrix

| Verification Dimension | Windows Reality (Reference) | Mac Reality (Physical Measurement) | Parity Status |
|---|---|---|---|
| **Candidate Source Delta** | `server/app.py`, `scripts/courier_verifier.py`, `scripts/windows_worker/daemon.py` | Identical source tree tested in scratch clone | **PARITY CONFIRMED** |
| **Artifact Store Endpoint** | `/artifacts` (Upload bytes, return `artifact_id`, content-addressed `blobs/`) | Verified on port 8081: `art-e626b7...` (A) and `art-b6b6b4...` (B) | **PARITY CONFIRMED** |
| **Artifact Hash Verification** | Verified via `test_artifact_upload_flow.py` (23/23 passing) | Verified via independent `courier_verifier` logic re-hashing server bytes | **PARITY CONFIRMED** |
| **Duplicate Result Protection** | Resend of stored `dispatch_id`/`result_id` returns `ACK_DUPLICATE`; conflict returns 409 | Verified in `test_p3_server_idempotency.py` (8/8 passing) & live REST API | **PARITY CONFIRMED** |
| **Automated Step Transition** | `goal.current_step_index` advances 0 $\to$ 1 on `verify(PASS)` | Verified live: Step A `RECONCILED` $\to$ Step B auto-dispatched to `MAC-01` | **PARITY CONFIRMED** |
| **Human Relay Interventions** | 0 relays | 0 manual prompts, 0 manual API resumes (`HUMAN_RELAY_COUNT=0`) | **PARITY CONFIRMED** |
| **Crash Survival / No-Replay** | `RESULT_RECEIVED` persists across crash; re-claim checks duplicate | Server PID 4710 killed with `SIGKILL`; restarted PID 4722; state loaded byte-identical; Task A never replayed | **PARITY CONFIRMED** |
| **Headless AI CLI Execution** | Windows worker PowerShell base64 execution | `agy` 1.2.11: 100% headless (10.2s); `muse` 1.4.0: gated on browser OAuth | **ASYMMETRY IDENTIFIED** |

---

## 2. Test Execution Summary

Running the 79 Candidate B-2 targeted tests on physical Darwin hardware:
```
============================= test session starts ==============================
platform darwin -- Python 3.9.13, pytest-8.4.2, pluggy-1.6.0
rootdir: candidate_b_2
collected 79 items

tests/test_p3_server_idempotency.py ........                             [ 10%]
tests/test_artifact_upload_flow.py .......................               [ 39%]
tests/test_artifact_store.py ..............................              [ 77%]
tests/test_integration_contract.py ........                              [ 87%]
tests/test_mac_worker_contract.py ..........                             [100%]

============================= 79 passed in 14.34s ==============================
```

---

## 3. Commercial Pilot Presentation Card (Grandma / Mama Alignment)

### First Sentence:
> **„Ich programmiere etwas Neues.“**

### Visual 60-Second Storyboard:
1. **0:00 - 0:10 (The Customer Promise)**: Grandma sees one single window with 6 clear states: `AUFTRAG: 1` · `ALS NÄCHSTES: 1`. Zero technical clutter.
2. **0:10 - 0:25 (Autonomous Step 1)**: System takes on Step 1 (`task-canary-A`). Artifact `canary_A.txt` (`COURIER-A2B-A`) is uploaded to the tamper-evident store.
3. **0:25 - 0:35 (Independent Quality Verification)**: The independent Verifier examines server-side bytes and calculates SHA-256 (`575114...`). Verifier issues `PASS`. Task 1 reaches `RECONCILED`.
4. **0:35 - 0:50 (Zero-Human Automatic Continuation)**: Without touching the keyboard, Step 2 (`task-canary-B`) begins immediately. `HUMAN_RELAY_COUNT = 0`.
5. **0:50 - 1:00 (Crash Resilience & Completion)**: Violent power loss injected via `SIGKILL`. On restart, the system resumes smoothly at Step 2 without re-running Step 1. Both steps reach `RECONCILED`. Goal is `DONE`.

---

## 4. Current Stopping Gates (Prioritized)

1. **`AUTH-MUSE-CLI-DEVICE-OAUTH-GATE`** (Human/Security Gate):
   - `/Users/user/.local/bin/muse` requires one-time interactive OAuth device login at `https://auth.meta.com/oauth/device`.
   - Alternatively, workers can use `/Users/user/.local/bin/agy` which is already verified 100% headless and responsive.
2. **`PORT-8080-CANONICAL-SERVER-CUTOVER-GATE`** (Physical Canary Authorization Gate):
   - Production port 8080 is governed by macOS launchd service `com.courier.server` (PID 69407, KeepAlive=true).
   - Cutover from obsolete commit `332a42f9` to `candidate-b-2` requires operator authorization to reload launchd.
3. **`DARWIN-CLEANUP-GROUP-PERMISSION-DEFECT`** (Writer Delta):
   - `scripts/mac_worker/runtime_state.py:112` raises `PermissionError` on `os.killpg` during supervisor teardown.
   - Pinned for Windows source writer to add `except (ProcessLookupError, PermissionError):` fallback.
