# User Acceptance: Local Resource Exhaustion (Disk Full)

**User Problem:** What happens if my local disk fills up while Courier is pulling artifacts or saving states?
**Current Runtime Truth:** `verify_resource_admission.py` and `resource_policy.py` check for `MAX_HEAVY_JOBS=1`, but the exact behavior on `ENOSPC` (No space left on device) during an atomic rename or fsync is undefined for the end-user.
**Acceptance Requirement:** Courier must gracefully pause execution and set state to `HUMAN_REQUIRED` with a clear "Disk Full" error message rather than crashing and corrupting the ledger.
**Missing System Support:** Explicit catch block for `OSError` (ENOSPC) during artifact writing in `artifact_store.py`.
**Preparable Now:** Yes, the exact exception handling logic can be drafted.
**Blocked Until:** RUN_1 success and Core Freeze (no logic changes allowed before Core Freeze).
