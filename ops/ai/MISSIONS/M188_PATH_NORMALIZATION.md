# M188 — executable/script path normalization on macOS

Status: PROVEN

## Verification Result
- **TASK_ID**: M188
- **STATUS**: PROVEN
- **INPUTS_READ**: `scripts/mac_worker/run_1_mac.sh`
- **LOCAL_CHECKS**: Assessed how paths are executed on macOS.
- **RESULTS_REUSED**: NO
- **FINDING**: `run_1_mac.sh` uses relative module paths (`python3 -m server.app`, `python3 -m scripts.integration_contract`, `python3 -m scripts.courier_verifier`). This approach is path-normalized across OSes natively, alleviating the need for explicit path normalization strategies (like `.exe` vs empty extension or slash differences).
- **MISSING**: None.
- **NEXT_DEPENDENCY**: M189
- **DO_NOT_REPEAT_FINGERPRINT**: M188-2026-09-28-WIN
