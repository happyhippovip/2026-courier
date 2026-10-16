# MMAC-204 — #228 bootstrap credential truth verified (universal continuation, read-only)

Base `origin/integration/v1` = `f425d328`. Cursor L6 scope, branch idle 2.5h — read-only audit, zero touches. All four installer-tracked PRs still OPEN (#228, #246, #240, #245); trunk unchanged.

## Verdict: VERIFIED genuine, fully green, no action
- Credential file moves out of the source tree (`workerDir/config.json`) into `%LOCALAPPDATA%/Courier/config.json` with merge-preserve semantics, corrupt-config fail-closed (exit 1), SecureString prompt, and no false "stored securely" claim.
- Health wait is truthful: watches only new `daemon.log` bytes for FATAL (exit 1); timeout reports "health NOT verified" with exit 2. The old `"Registered successfully"` wait (a line `daemon.py` never emits) and log destroy/create are gone.
- Strongest element: the contract test cross-asserts that every `-match "MARKER"` in the health section exists in `daemon.py` — this closes the false-wait bug class generically, not just the one instance. Windows-only native merge test is skip-gated and executed on Windows CI (PASS 11m28s / 9m25s).
