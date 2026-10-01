# WP005: Pytest Temp Handle Leak on Windows

## Target
`tests/test_*.py`
`conftest.py`

## Defect
When running `pytest` on Windows (`MUSE_WINDOWS`), the test session crashes during teardown with `PermissionError: [WinError 5] Zugriff verweigert: ... pytest-current`. This indicates that one or more tests are leaking file handles or spawning background processes that hold locks on files within the `pytest-of-<user>` temporary directory, preventing pytest from cleaning up symlinks/directories.

## Instructions for SOLE_WINDOWS_WRITER
1. Audit tests that use `subprocess.Popen` or create background daemon threads (e.g., `test_mac_worker_contract.py`, `test_muse_supervisor.py`).
2. Ensure that all processes spawned in tests are explicitly terminated and wait()ed upon in `finally` blocks or pytest fixtures with teardown logic.
3. Close all open file descriptors. On Windows, a lingering subprocess inheriting standard handles will lock the parent's temporary files.
4. Verify by running `python -m pytest tests/` (ignoring posix-only errors) and checking that the teardown completes without `WinError 5`.

## Causal Path
Windows strictly locks files that have active handles (unlike Linux which allows deletion of unlinked files). When Courier tests leak child processes or file descriptors, the OS denies `pytest_sessionfinish` the ability to clean up the `pytest-current` symlink.
