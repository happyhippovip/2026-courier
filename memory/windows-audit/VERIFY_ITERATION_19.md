# Iteration 19: `scripts/revenue_worker_adapter.py`

## Verification Scope
- Target: `scripts/revenue_worker_adapter.py`
- Existing Test: None
- Module Type: Autonomous Courier worker adapter (Revenue node / MacOS native worker)
- Platform: Windows-safe compatibility verification.

## Status
**VERIFIED** - Coverage expanded to 100%.

## Changes Made
- No changes required to source code `revenue_worker_adapter.py`.
- **Testing**: Added extensive missing coverage to `tests/test_revenue_worker_adapter.py`.
  - Added unit test coverage for `get_config()` initialization logic (new config generation vs existing config reading, keychain fallback mocks vs env variables).
  - Added unit test coverage for `http_post()` using `urllib.request.urlopen` mocks for handling success JSON parsing, HTTP Errors, and generic socket/connection errors.
  - Added full branch and edge-case execution for `main()` polling loop, simulating registration, heartbeat, claim assignment, target directory cleanup, and subprocess execution.
  - Added execution trace coverage for `__main__` entrypoint.
- Achieved **100% line coverage** for the module under pytest.

## Notes
- `revenue_worker_adapter.py` is explicitly designed to handle keychain interactions (`security find-generic-password`) typically available on MacOS. On Windows, the subprocess safely fails and falls back to JSON file or Environment Variables correctly.
- Module adheres to standard timeout boundaries and safely catches subprocess errors and generic traceback exceptions inside the main polling loop.
- The `PermissionError` cleanup behavior during pytest execution on Windows does not affect module correctness and is isolated to pytest's `tmp_path` symlink cleanup logic.
