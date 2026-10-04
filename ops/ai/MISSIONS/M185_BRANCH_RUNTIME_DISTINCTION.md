# M185 — branch/ref vs loaded runtime distinction

Status: PROVEN

## Verification Result
- **TASK_ID**: M185
- **STATUS**: PROVEN
- **INPUTS_READ**: `ops/ai/MAC_EXACT_BINDING_INPUTS.md`, `scripts/mac_worker/run_1_mac.sh`
- **LOCAL_CHECKS**: Validated that `run_1_mac.sh` checks out the designated reference prior to initiating execution.
- **RESULTS_REUSED**: NO
- **FINDING**: `run_1_mac.sh` executes `git checkout coordination/mac-handoff-20260928` prior to script launch. `FINAL_SHA` checks and binding values ensure the checkout matches `3c2aa516...`. This creates a solid boundary distinguishing the checked out ref and the runtime loaded.
- **MISSING**: None.
- **NEXT_DEPENDENCY**: M186
- **DO_NOT_REPEAT_FINGERPRINT**: M185-2026-09-28-WIN
