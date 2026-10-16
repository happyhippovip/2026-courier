# MMAC-197 — Ledger blind-fallback honesty fix (WINDOW 3, writer unit)

Base `origin/integration/v1` = `f425d328`. Scope was FREE: PR #234 branch idle 2.5h, CI settled green, no active writer. Work in isolated worktree `/tmp/muse-gov`; shared checkout (foreign branch + scratch) untouched.

## Boundary audited first (read-only)
- #214 (host_health) and #234 (resource_governor) CI all-SUCCESS both platforms — no action.
- #231 (L2 TaskPacket single-writer) proof genuine: parked_from memory + CURRENT normalization + 8-step sequence and 5-seed fuzz asserting ≤1 CURRENT. Closes the single-writer half of MMAC-196/U5-PARTIAL. No action.
- #227/#233 golden lanes CI-green, test-only. No action.
- Earliest genuinely unverified boundary: #234's Windows claim is mock-only — `test_measure_pressure_windows_psutil_fallback` monkeypatches psutil, so the blind-host sub-case (psutil missing) was never exercised and reported healthy GREEN.

## Defect → fix
- `scripts/resource_governor.py`: psutil-missing `except` returned `"GREEN"` while measuring nothing → now `"UNKNOWN"` (outer-handler precedent). Admission-neutral (`admit_job` admits both; `get_poll_interval` defaults to base on unknown states).
- Regression `test_blind_measurement_reports_unknown_not_green`: FAILED red pre-fix (`-UNKNOWN +GREEN`), 7/7 green post-fix in 0.11s.
- Ledger doc: appended defect-4 bullet under `## scripts/resource_governor.py` (family convention).

## Delivery
Commit `707f7484a`, pushed `df11940bf..707f7484a` to `muse/MUSE-ledger-resource-governor` → updates open PR #234, no new PR. Commit hook: Ledger integrity passed.

## Explicitly not claimed
Real-Windows `psutil.cpu_percent(interval=None)` first-call semantics (returns ~0.0 first call → transient false GREEN) cannot be verified from this Mac; left for a Windows-host owner. No Windows shell used here; no results invented.
