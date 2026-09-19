FALSE_GREEN_AUDIT=FAIL
FIRST_FALSE_GREEN=scripts/runtime_truth.py / get_sha
REPRO=Modify the codebase and commit while a worker process is running. `get_sha` executes `git rev-parse HEAD` on the local disk instead of returning the actual loaded runtime identity. This falsely returns the new SHA and displays a "green" acceptance for a candidate that is not actually executing in memory.
MINIMAL_FIX=The runtime identity (SHA) must be injected into the process at startup (e.g., via environment variable or static build manifest) and reported from memory, ignoring the current disk `.git` state.
