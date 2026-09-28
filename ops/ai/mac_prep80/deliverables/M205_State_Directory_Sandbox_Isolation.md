# M205 — State Directory Sandbox Isolation

## 1. Overview & Authority
- **Task ID**: M205
- **Area**: STATE_SANDBOX
- **Status**: COMPLETE

## 2. Sandbox Rules
- Dedicated state root: `server/state/isolated_run1`.
- Read-only parent boundaries: Code files in `server/app.py` cannot be modified by state writes.
- Write access restricted strictly to child state directory.
