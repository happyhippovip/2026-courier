# WP004: POSIX Process Isolation in mac_worker

## Target
`scripts/mac_worker/runtime_state.py`
`tests/test_m201_process_identity.py`
`tests/test_muse_convergence.py`

## Defect
`runtime_state.py` relies heavily on POSIX-specific process management capabilities that crash immediately on Windows:
1. `import fcntl` (Raises `ModuleNotFoundError` on Windows)
2. `os.killpg` (Raises `AttributeError: module 'os' has no attribute 'killpg'` on Windows)
3. Shelling out to `ps -p <pid> -o ...` (Windows `ps` equivalent is `tasklist` or PowerShell `Get-Process`, which has completely different outputs).

## Instructions for SOLE_WINDOWS_WRITER
1. Update `scripts/mac_worker/runtime_state.py` to gracefully fail or mock out POSIX features when `os.name == 'nt'`.
2. Consider wrapping `import fcntl` in a `try/except ImportError` block and falling back to `portalocker.lock` if file locking is strictly needed on Windows, or just returning a mock lock.
3. Stub `process_identity`, `group_exists`, and `cleanup_group` on Windows if cross-platform process isolation is not strictly required for local tests. 
4. Update `tests/test_m201_process_identity.py` and `test_muse_convergence.py` to `pytest.mark.skipif(os.name == 'nt', reason="Requires POSIX process management")` to avoid test collection/execution failures on `MUSE_WINDOWS` nodes.

## Causal Path
The Courier project uses a `mac_worker` module that was strictly meant for Mac execution. However, tests in the generic `tests/` folder import these modules and crash during the `pytest` collection phase on Windows, breaking the test suite for Windows nodes.
