# Mac Exact Binding Specification for FINAL_SHA — 2026-09-28

**Task ID**: PPREP-01  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: PROVEN & READY FOR FINAL_SHA  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  
**Workspace**: `/Users/user/Downloads/2026-courier`  

---

## 1. Objective

Provide the exact, deterministic binding procedure to attach the Mac physical test environment and verification harness to the final candidate commit (`FINAL_SHA`) as soon as Windows Central Writer commits the 5-file patch.

---

## 2. Pre-Binding Environmental Invariants

Before binding to `FINAL_SHA`, the Mac worker must deterministically assert:

1. **Repo Lineage Integrity**:
   - Upstream remote: `origin` pointing to `https://github.com/happyhippovip/2026-courier.git`.
   - Base commit ancestor: `4c1e24ccc522042af826bc4c2b595daf85d097f9` (`origin/candidate-b-1`).
2. **Clean Application Working Tree**:
   - `git diff -- scripts/courier_verifier.py scripts/integration_contract.py server/app.py tests/test_artifact_upload_flow.py tests/test_p3_server_idempotency.py` must return 0 lines modified.
3. **Runtime Invariants**:
   - Python runtime: Python 3.9+ with `pytest`, `urllib`, `hashlib`, `json`, `sqlite3` available.
   - Network isolation: Staging port `8081` available (not bound by any zombie process).
   - Heavy job lock: `/tmp/courier_heavy_job.lock` free (`MAX_HEAVY_JOBS=1`).

---

## 3. Step-by-Step Binding Protocol

When Windows Central Writer publishes `FINAL_SHA`:

```bash
# Step 1: Fetch candidate lineage from origin
git fetch origin candidate-b-1

# Step 2: Validate that HEAD or remote tip matches FINAL_SHA
export FINAL_SHA=$(git rev-parse origin/candidate-b-1)
echo "Binding Mac verification to FINAL_SHA=${FINAL_SHA}"

# Step 3: Validate exact 5-file diff scope against base 4c1e24cc
git diff --name-only 4c1e24ccc522042af826bc4c2b595daf85d097f9 ${FINAL_SHA} > /tmp/candidate_files.txt
# Must contain strictly:
# - scripts/courier_verifier.py
# - scripts/integration_contract.py
# - tests/test_artifact_upload_flow.py
# - server/app.py
# - tests/test_p3_server_idempotency.py

# Step 4: Run whitespace check
git diff --check 4c1e24ccc522042af826bc4c2b595daf85d097f9 ${FINAL_SHA}
# Must exit 0 with 0 trailing whitespace violations

# Step 5: Fast post-patch targeted test execution
pytest tests/test_artifact_upload_flow.py tests/test_p3_server_idempotency.py tests/test_result_identity_binding.py tests/test_integration_contract.py -v
# Must report 44+ passed, SKIPPED=0
```

---

## 4. Binding Attestation Schema

Upon successful execution of the protocol, produce `ops/ai/wall_results/EXACT_MAC_BINDING_ATTESTATION.json`:

```json
{
  "binding_timestamp": "2026-09-28T...",
  "host": "MAC",
  "os": "Darwin 25.6.0 x86_64",
  "base_sha": "4c1e24ccc522042af826bc4c2b595daf85d097f9",
  "final_sha": "${FINAL_SHA}",
  "authorized_5_files_verified": true,
  "git_diff_check_clean": true,
  "targeted_tests_passed": 44,
  "skipped_count": 0,
  "binding_status": "EXACT_MAC_BINDING_LOCKED"
}
```
