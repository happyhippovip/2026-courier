# STATE/LOG/ARTIFACT ISOLATION RULES

## Core Tenet
Under no circumstances may execution RUN 1 and RUN 2 share identical ephemeral directories or write to global un-namespaced temporary files. Each execution must be strictly isolated to its respective `$TARGET_DIR`.

## Required Directory Structure
- `RUN_1` Base: `/tmp/courier_run1_{{FINAL_SHA}}/`
- `RUN_2` Base: `/tmp/courier_run2_{{FINAL_SHA}}/`

Each base must contain:
1. `evidence/` -> Read-only after execution.
2. `state/` -> Immutable state checkpoints, transferred strictly read-only into RUN 2.
3. `tmp/` -> Scoped entirely to that specific process tree. Cleaned upon SIGTERM/SIGINT.

## Validation Script
```bash
#!/usr/bin/env bash
# validates that no global /tmp/courier_xyz files leaked outside the bound SHA structure.
LEAKED=$(find /tmp -maxdepth 1 -name "courier_*" -not -name "courier_run1_{{FINAL_SHA}}" -not -name "courier_run2_{{FINAL_SHA}}")
if [ ! -z "$LEAKED" ]; then
    echo "Isolation violation detected. Unscoped files found:"
    echo "$LEAKED"
    exit 1
fi
```
