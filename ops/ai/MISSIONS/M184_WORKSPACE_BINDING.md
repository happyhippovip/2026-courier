# M184 — working-directory/repo-root binding

Status: PROVEN

## Verification Result
- **TASK_ID**: M184
- **STATUS**: PROVEN
- **INPUTS_READ**: `ops/ai/MAC_EXACT_BINDING_INPUTS.md`
- **LOCAL_CHECKS**: Checked if the `repo_root` binding exists and is specified correctly for Mac execution.
- **RESULTS_REUSED**: NO
- **FINDING**: `MAC_EXACT_BINDING_INPUTS.md` states: `BINDING_FIELD=repo_root, SOURCE=Mac worker filesystem, CURRENTLY_BINDABLE=YES`. The absolute path of the workspace on Mac will act as the binding value to prevent ambiguity.
- **MISSING**: None.
- **NEXT_DEPENDENCY**: M185
- **DO_NOT_REPEAT_FINGERPRINT**: M184-2026-09-28-WIN
