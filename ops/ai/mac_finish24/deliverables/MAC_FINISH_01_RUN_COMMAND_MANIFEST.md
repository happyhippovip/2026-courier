# MAC-FINISH-01 — Run Command Manifest Template

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-01
- **Area**: RUN_COMMAND_MANIFEST
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

This document provides the canonical Mac command manifest template for server, worker, verifier, and evidence capture, explicitly demarcating candidate-sensitive placeholders from invariant execution parameters.

---

## 2. Server Invocation Manifest
```bash
# Set isolated environment variables
export PORT=8081
export STATE_DIR=server/state/isolated_run1
export COURIER_AUTH_TOKEN=TEST_COURIER_AUTH_TOKEN_8081
export COURIER_VERIFIER_API_KEY=TEST_COURIER_VERIFIER_KEY_8081
export PYTHONUNBUFFERED=1

# Boot isolated coordinator server
python3 server/app.py > logs/run1_server.log 2>&1 &
SERVER_PID=$!
echo ${SERVER_PID} > server/state/staging.pid
```

---

## 3. Worker Invocation Manifest
```bash
# Execute isolated worker task poll and execution
python3 scripts/courier_verifier.py \
    --port 8081 \
    --task-id canary-task-a \
    --single-run \
    --auth-token TEST_COURIER_AUTH_TOKEN_8081 \
    > logs/run1_worker.log 2>&1
```

---

## 4. Verifier Invocation Manifest
```bash
# Trigger independent verifier execution
python3 scripts/courier_verifier.py \
    --port 8081 \
    --verify-only \
    --task-id canary-task-a \
    --expected-sha256 "<TASK_EXPECTED_SHA256>" \
    --api-key TEST_COURIER_VERIFIER_KEY_8081 \
    > logs/run1_verifier.log 2>&1
```

---

## 5. Evidence Capture Manifest
```bash
# Capture port state, memory usage, and artifact hashes
lsof -i :8081 > server/state/isolated_run1/port_evidence.txt
vm_stat > server/state/isolated_run1/memory_evidence.txt
shasum -a 256 server/state/isolated_run1/artifacts/* > server/state/isolated_run1/artifact_hashes.txt
```

---

## 6. Candidate-Sensitive Placeholders
- `<FINAL_SHA>`: Git commit hash of approved candidate (e.g. `34b0a4264bf763bc2a78f761ffba36e47706b2cf`).
- `<CANONICAL_BUNDLE_REF>`: Ref or tarball path containing approved candidate codebase.
- `<TASK_EXPECTED_SHA256>`: Pre-declared artifact hash in goal contract.
- `<TARGETED_TEST_SUITE>`: Canonical test runner command filter.
