# M193: Temporary-File Cleanup Boundaries

## Finding
When saving state or snapshots using atomic `os.replace`, scripts generate temporary files. There are two distinct cleanup boundary strategies in use within the 2026-courier repository:

1. **Fixed-suffix temporary files (`.tmp`)**: 
   - Used by `server/app.py`, `run_bodyguards.py`, and `run_thought_ingestion.py`.
   - Temporary filename is deterministic (e.g., `state.json.tmp`).
   - If the process crashes mid-write (before `os.replace`), a `.tmp` file is orphaned.
   - However, on the next invocation, the `open(..., 'w')` call overwrites the existing `.tmp` file.
   - **Boundary limit**: 1 orphaned file per target file. No unbound storage leak.

2. **Randomized/PID-based temporary files (`.tmp.<pid>.<uuid>`, `snap-tmp-<hash>`)**:
   - Used by `run_chief_commander.py` and `run_context_sync.py` (via `tempfile.mkstemp(prefix="snap-tmp-")`).
   - Temporary filename is random per invocation.
   - While `run_context_sync.py` attempts cleanup via a `try...finally` block (`os.unlink(temp_path)`), a hard process crash (e.g. `SIGKILL`, system panic) skips `finally`.
   - `run_chief_commander.py` has no explicit cleanup for its UUID-based temp files.
   - **Boundary limit**: Unbounded. Successive crashes will permanently leak files into the state/snapshot directory, eventually exhausting storage or inode limits if crashes are frequent.

## Local Check
We executed `tests/test_m193_temp_file_cleanup.py` which accurately modelled both approaches.
- Generating a UUID/PID-based file without `os.replace` completion leaves a unique file on every iteration.
- Generating a fixed `.tmp` file bounds the leak to a single file that gets safely truncated/overwritten upon the next attempt.

## Conclusion
The temporary-file cleanup boundary for most of the application is bounded by deterministic filenames. However, the randomized temporary names in `run_chief_commander.py` and `run_context_sync.py` present an unbounded leak risk under hard-crash scenarios.

STATUS=PROVEN
