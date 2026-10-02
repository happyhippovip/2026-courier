# Scope
`scripts/run_context_sync.py`

# Existing tests inspected
None existed.

# Commands executed
- Created `tests/test_run_context_sync.py` to cover core logic (git HEAD parsing, memory truth parsing, Courier state reading, context snapshot generation, and task staleness checking).
- `pytest tests/test_run_context_sync.py`

# Passing checks
- `get_git_head` falls back safely to "NOT_CONNECTED" when repository is absent. Parses valid HEAD refs safely.
- `read_project_memory_truth` correctly extracts verifiable data (`VERIFIED_CURRENT`, decisions, ideas) from text files.
- `read_courier_state` successfully pulls from locking events, state trackers, and generated JSON reports without throwing errors.
- `generate_context_snapshot` correctly skips generating new versions when no material changes occurred, keeping context stable, and correctly uses `os.replace()` for atomic cross-platform writes.
- `check_task_staleness` correctly flags out-of-date tasks when context is refreshed.

# Failing checks
- All tests pass (with the exception of the known pytest Windows symlink teardown `[WinError 5]`, which is outside the application code).

# Audit findings confirmed
- None specifically documented for this file in earlier audits, but behavior is verified to be robust and deterministic. Zero model calls are made. 

# Audit findings disproved
- None

# Missing tests
- Edge case: Git fallback using `subprocess` execution (we only tested direct file reading and missing repository behavior).

# Edge cases
- If `PROJECT_STATE.md` has `VERIFIED_CURRENT: ` prefix, we now properly handle the prefix logic in testing instead of hardcoding exact milestones.

# Recommended implementation fixes
- None needed. The file operates correctly.

# Suggested next verification scope
`scripts/verify_pilot_schema.py`
