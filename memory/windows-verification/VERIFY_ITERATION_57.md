# Verification Report: q14_proof.py

## Scope
- Module: `scripts/q14_proof.py`
- Objective: Verify Windows compatibility, test coverage, and deterministic execution of the q14 proof script (which validates task routing logic by capabilities).

## Findings
- **Module Design:** The script sets up an environment, runs the main Flask app in a background thread, and uses `urllib.request` to test HTTP endpoints directly.
- **Execution Paths:** It accurately simulates placing heterogeneous goals into the task queue (Windows/Linux) and then having a Linux worker claim only the linux tasks.
- **Environment Notes:** Natively it attempts to import `server.app`, which fails if the repo root is not on `sys.path`.
- **Tests**: Created `tests/test_q14_proof.py` replacing the missing test coverage. The test mocks `threading.Thread` and `urllib.request.urlopen` to test the procedural logic of the script deterministically without spawning an actual server on an open port, protecting test suites from port collision flakiness. The tests run natively on Windows with 0 errors.

## Conclusion
The module `scripts/q14_proof.py` is verified. It safely validates the capabilities routing implementation in the core server.
