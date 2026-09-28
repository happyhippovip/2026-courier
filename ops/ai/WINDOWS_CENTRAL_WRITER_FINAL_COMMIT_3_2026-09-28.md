# Windows Central Writer - Third Batch of 3 Substeps

In response to the requirement to perform at least 3 concrete substeps per pass as the primary worker on Windows, we completed the following 3 distinct fixes directly on the `2026-courier` repo, and generated 1 patch for an out-of-jurisdiction bug.

### 1. Windows Worker Lock File Leak & PermissionError (Bug Fix)
- **Problem**: In `scripts/windows_worker/daemon.py`, the `acquire_lock` function uses `msvcrt.locking(fd)` to hold a non-blocking lock. In the `finally:` block of `loop()`, it tries to `os.remove(lock_path)`. On Windows, deleting an open/locked file triggers a `PermissionError` (Access is denied), causing the worker to crash with a traceback and leaving the lock file orphaned, effectively bricking future restarts.
- **Fix**: Added explicit `os.close(_lock_fd)` in the `finally:` block before attempting to `os.remove(lock_path)`, wrapped in a safe `try/except` block to prevent exceptions during shutdown.
- **Evidence**: Fix directly implemented in `scripts/windows_worker/daemon.py`.

### 2. Windows Worker Subprocess Leak on Timeout (Bug Fix)
- **Problem**: In `scripts/windows_worker/daemon.py`, `run_task` uses `process = subprocess.Popen(...)` and `process.communicate(timeout=600)`. When this times out, `subprocess.TimeoutExpired` is thrown, caught by the generic `except Exception as e`, and the function returns `FAILED`. However, the child process is **never killed**, leaving infinite headless PowerShell processes running in the background and accumulating zombie tasks on the host.
- **Fix**: Added `process.kill()` and `process.communicate()` in the `except` block of `run_task` to ensure the process is forcefully terminated before returning.
- **Evidence**: Implemented the kill logic within the exception handler.

### 3. Windows Worker Timeout Leak (Missing Test)
- **Problem**: The process kill logic added above was completely untested in the worker contract test suite.
- **Fix**: Added `test_run_task_kills_process_on_timeout` in `tests/test_windows_worker_contract.py` which mocks a `subprocess.Popen` object that times out, and asserts that `kill()` was explicitly invoked on the object.
- **Evidence**: Verified local testing passed.

### Out of Jurisdiction: Mac Worker Subprocess Leak
- **Problem**: While investigating the Windows worker, I noticed that `scripts/mac_worker/daemon.py` suffers from the *exact same* subprocess leak in `run_agy` (it catches `Exception` but fails to kill the `agy` process). 
- **Action**: Because I am strictly the "Windows Central Writer", I am not authorized to fix the Mac worker. I have created an exact patch package: `ops/ai/MAC_WORKER_TIMEOUT_LEAK.patch`.

---
Commit SHA: (Pending commit)
All tests (`pytest tests/`) are 100% passing across the suite.
