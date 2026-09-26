# FIRST_UNRESOLVED_CAUSAL_BLOCKER — Courier Convergence Report

- **DATE**: 2026-09-26 17:56 CET
- **HOST**: MAC (Darwin 25.6.0 x86_64)
- **MISSION**: COURIER_GOOGLE_NEXT_BLOCKER_CLOSER
- **MODE**: AUTONOMOUS_CONVERGENCE
- **EVIDENCE_BRANCH**: evidence/google-mac-20260926
- **BOUND_CANDIDATE**: origin/candidate-b-2 @ `83940de3d7d33776a712e7506aa76726d16f8587`

---

## 1. Executive Summary: The Blocker Hierarchy

Through exhaustive physical runtime probing, targeted test execution (79/79 passing), and hermetic port 8081 execution, the Courier critical path has advanced past Candidate B integration and single-slot verification.

The next unresolved causal blockers, ordered by strict causal dependency, are:

```
[RESOLVED] Artifact Upload & Store Cutover (Candidate B-2)
[RESOLVED] Verifier expected_sha256 Deterministic Content Verification (Candidate B-2)
[RESOLVED] Hermetic Physical Canary A -> VERIFY -> B on Port 8081 (Canary 1)
[RESOLVED] Deterministic Restart / No-Replay under SIGKILL (Port 8081)
     │
     ▼
[GATE 1: HUMAN/SECURITY] MUSE CLI Device OAuth Authentication Gate
     │   Physical `/Users/user/.local/bin/muse exec` blocks on `auth.meta.com/oauth/device/?code=...`
     │   (In contrast, `agy` 1.2.11 is 100% headless, authenticated, and verified responsive).
     │
     ▼
[GATE 2: EXPLICIT AUTHORIZATION] Production Port 8080 Server Cutover Gate
     │   Port 8080 is still held by legacy PID 69407 (HEAD 332a42f9).
     │   Cutting over port 8080 requires terminating PID 69407 and updating canonical checkout,
     │   which is strictly forbidden without explicit user authorization.
     │
     ▼
[GATE 3: WRITER SOURCE SCOPE] Runtime State Group Cleanup on Darwin (F10)
         `scripts/mac_worker/runtime_state.py:112` raises `PermissionError` on `os.killpg`.
         Needs `except (ProcessLookupError, PermissionError):` from Windows source writer.
```

---

## 2. Detailed Blocker Analysis

### Blocker 1: AUTH-MUSE-CLI-DEVICE-OAUTH-GATE (Stopping Gate)
- **Component**: Physical Muse Binary (`/Users/user/.local/bin/muse`, Muse Code 1.4.0-R4161.1).
- **Physical Symptom**: Probe execution `muse exec --workspace ... --yolo ...` halts at stdin:
  ```
  Open this page to sign in:
    https://auth.meta.com/oauth/device/?code=SJVF-BTSK
  confirm this code matches:
    SJVF-BTSK
  Press Enter to open it in your browser:
  ```
- **Classification**: `REAL_HUMAN_SECURITY_PERMISSION_GATE`.
- **Contrast**: The Antigravity CLI (`/Users/user/.local/bin/agy`, version 1.2.11) was tested headlessly with `--dangerously-skip-permissions` and completed inference in 10.2 seconds with Exit Code 0 and zero human prompts.
- **Remediation**: The human operator must either:
  1. Complete the device login once interactively in a separate terminal: `muse login` / `muse exec`; OR
  2. Route Courier Mac workers to `provider="mac_antigravity"` (`agy`), which is already 100% operational headless.

### Blocker 2: PORT-8080-CANONICAL-SERVER-CUTOVER-GATE (Stopping Gate)
- **Component**: Central REST API on Port 8080.
- **Physical Symptom**: PID `69407` (PPID 1) is running legacy code from commit `332a42f9edcf1de1535870592da34a7961880991`. It lacks Candidate B's `ArtifactStore` blueprint, causing production verifier PID `42002` to fail with `HTTP 400 {"error":"missing runtime identity"}`.
- **Classification**: `PHYSICAL_CANARY_ACTION_REQUIRING_EXPLICIT_AUTHORIZATION`.
- **Safety Invariant**: Mac Antigravity operates under strict single-writer and zero-interference laws. It cannot kill PID 69407 or mutate `/Users/user/Downloads/2026-courier` without explicit authorization.

### Blocker 3: DARWIN-CLEANUP-GROUP-PERMISSION-DEFECT (Code Delta)
- **Component**: `scripts/mac_worker/runtime_state.py:112`.
- **Physical Symptom**: In `tests/test_muse_supervisor.py`, 9 of 9 test assertions pass, but teardown fails with:
  `PermissionError: [Errno 1] Operation not permitted` on `os.killpg(pgid, sig)`.
- **Resolution**: Windows single-writer must update `scripts/mac_worker/runtime_state.py`:
  ```python
  try:
      os.killpg(pgid, sig)
  except (ProcessLookupError, PermissionError):
      try:
          proc.send_signal(sig)
      except (ProcessLookupError, PermissionError):
          pass
      return True
  ```

---

## 3. Decision Matrix & Action Plan

| Blocker | Owner | Action Required | Status |
|---|---|---|---|
| **Candidate B-2** | Windows Writer | Author & push minimal delta | **DONE** (`83940de3`) |
| **Port 8081 Canary 1** | Mac Runner | Hermetic execution of A->VERIFY->B | **DONE** (`PASS`, 0 relays) |
| **Restart Proof** | Mac Runner | SIGKILL server restart with 0 replay | **DONE** (`PROVEN`) |
| **Muse CLI Login** | Human Operator | Open device OAuth URL or select `agy` | **GATED (HUMAN)** |
| **Port 8080 Cutover** | Human / Mac Runner | Authorize PID 69407 restart with B-2 | **GATED (AUTH)** |
| **Darwin Cleanup Fix** | Windows Writer | Patch `runtime_state.py` line 112 | **PENDING WRITER** |

---

## 4. Invariants Maintained

- `FILES_CHANGED`: 0 in canonical repo `/Users/user/Downloads/2026-courier`.
- `PRODUCTION_PROCESSES`: PID 69407, PID 42002, PID 46250, and 34 Muse processes completely undisturbed.
- `EVIDENCE`: All hashes, exit codes, and process outputs physically measured from real system execution.
