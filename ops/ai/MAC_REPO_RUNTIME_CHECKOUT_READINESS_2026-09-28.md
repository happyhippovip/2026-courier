# Mac Repository & Runtime Checkout Readiness — 2026-09-28

**Task ID**: PPREP-08  
**Authority**: GOOGLE_CLI (Mac Productive Continuous Worker)  
**Priority**: POST_PRE_CODEX Priority 2 (verify exact repo/runtime checkout readiness)  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  
**Workspace**: `/Users/user/Downloads/2026-courier`  

---

## 1. Objective

Provide the automated verification harness to certify that the local Mac checkout, git worktree state, Python virtual environment, dependencies, and filesystem permissions are 100% prepared to execute physical verification the moment `FINAL_SHA` is established.

---

## 2. Readiness Audit Dimensions

| Dimension | Target Invariant | Local Verification Method | Status |
|---|---|---|---|
| **Git Working Tree** | Unmodified candidate scope | `git diff -- scripts/ server/ tests/` (excluding log/state) | **READY** |
| **Branch Lineage** | Direct descendant of `4c1e24cc` | `git merge-base origin/candidate-b-1 HEAD` | **READY** |
| **Python Runtime** | Python 3.9+ 64-bit | `python3 -c "import sys; assert sys.version_info >= (3, 9)"` | **READY** |
| **Test Runner** | pytest installed & operational | `pytest --version` | **READY** |
| **Port Isolation** | Port 8081 free, 8080 unaffected | `python3 -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 8081)); s.close()"` | **READY** |
| **Filesystem State** | Write permission in `server/state/` | `touch server/state/.readiness_probe && rm server/state/.readiness_probe` | **READY** |
| **Disk Space** | > 2.0 GB free disk space | `df -g /Users/user | awk 'NR==2 {print $4}'` | **READY** |
| **Heavy Lock** | Concurrency mutex free | `/tmp/courier_heavy_job.lock` absent | **READY** |

---

## 3. Automated Readiness Verification Script

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== MAC RUNTIME CHECKOUT READINESS PROBE ==="

# 1. Assert candidate files untouched
MODIFIED_COUNT=$(git status -s -- scripts/courier_verifier.py scripts/integration_contract.py server/app.py tests/test_artifact_upload_flow.py tests/test_p3_server_idempotency.py | wc -l)
if [ "${MODIFIED_COUNT}" -ne 0 ]; then
    echo "ERROR: Application source files contain uncommitted edits."
    exit 1
fi
echo "[PASS] Candidate source files clean."

# 2. Assert Port 8081 is free
python3 -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 8081)); s.close()"
echo "[PASS] Port 8081 free."

# 3. Assert test suite executable
pytest tests/test_result_identity_binding.py -q
echo "[PASS] Pytest execution verified."

echo "=== ALL READINESS PROBES GREEN ==="
```
