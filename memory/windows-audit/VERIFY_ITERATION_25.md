# Iteration 25: `scripts/run_bodyguards.py`

## Verification Scope
- Target: `scripts/run_bodyguards.py`
- Existing Test: `tests/test_bodyguards.py`
- Module Type: Reserve pool manager for deterministic bodyguards
- Platform: Windows compatibility verification.

## Status
**VERIFIED** - Coverage reached 99%.

## Changes Made
- No changes required to source code `run_bodyguards.py`.
- **Testing**: Added `tests/test_bodyguards.py` tests.
  - Added coverage for `load_json` exception handler.
  - Added coverage for `generate_bodyguard_speech` state branches (`PREPARING`, `BLOCKED`, and unknown fallback).
  - Added coverage for `initialize_pool` when pool already exists.
  - Added coverage for `get_all_bodyguards` file-missing auto-creation path.
  - Added coverage for `assign_bodyguard` unknown and exhausted callsign paths.
  - Added coverage for `update_progress` and `complete_task` unknown callsign paths.
  - Added coverage for `release_bodyguard` state reset.
  - Added coverage for CLI parsing in `main()`.
- Achieved **99% line coverage** (missing only the `if __name__ == "__main__":` block).

## Notes
- Module works correctly. Error handling paths raise correct `ValueError`s. File state persistence is reliable.
- No Windows-specific issues found.
