# M187 — environment-variable allowlist fingerprint plan without secret values

Status: PROVEN

## Verification Result
- **TASK_ID**: M187
- **STATUS**: PROVEN
- **INPUTS_READ**: `ops/ai/MAC_EXACT_BINDING_INPUTS.md`
- **LOCAL_CHECKS**: Checked if environment variables carry secrets.
- **RESULTS_REUSED**: NO
- **FINDING**: The main environment variable needed for the Mac worker is `COURIER_API_KEY`. As specified in `MAC_EXACT_BINDING_INPUTS.md`, `COURIER_API_KEY` is provided by the Mac Worker host. Fingerprinting will only check the keys' presence (`"COURIER_API_KEY" in os.environ`) without emitting the secret value to the logs.
- **MISSING**: None.
- **NEXT_DEPENDENCY**: M188
- **DO_NOT_REPEAT_FINGERPRINT**: M187-2026-09-28-WIN
