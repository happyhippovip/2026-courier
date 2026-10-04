# MAC PHYSICAL OWNER HANDOFF

## IDENTIFICATION
REVIEWED_SHA=9dba150538eb971e4a27c1e8f7806be13ede1a7a
REMOTE_SHA=9dba150538eb971e4a27c1e8f7806be13ede1a7a
EXPECTED_LOCAL_SHA=9dba150538eb971e4a27c1e8f7806be13ede1a7a
EXPECTED_BOUND_SHA=9dba150538eb971e4a27c1e8f7806be13ede1a7a

## PRE-RUN GO CHECKLIST
1. Verify exact SHA on Mac physical machine matches REVIEWED_SHA (9dba150538eb971e4a27c1e8f7806be13ede1a7a).
2. Verify worktree is completely clean. No untracked `.py` or `.sh` files in core directories.
3. Check out the exact SHA (do NOT run on a moving branch).
4. Verify port 8080 (or intended communication port) is accessible for `server/app.py`.
5. Ensure `pytest tests/` was successful across the local Windows test suite to confirm core logic.

## ABORT IF
- `git status` shows any modified, tracked files before run.
- The SHA does not match exactly.
- Network to the central API/Server is unreachable.
- Any physical tampering or manual editing is required to start the run.

## RUN1 COMMAND TEMPLATE
```bash
git checkout 9dba150538eb971e4a27c1e8f7806be13ede1a7a
bash scripts/mac_worker/run_1_mac.sh
```

## EVIDENCE TO CAPTURE
1. `artifact.json` output exactly as written by the worker.
2. The stdout/stderr logs from the bash execution.
3. Local file system state representation of `work_dir/` after the run.

## PASS CONTRACT
- The `artifact.json` successfully hits the central server API or is written correctly to disk with correct payload format.
- The script exits with code 0.
- Exactly-once execution occurs without zombie processes.

## FAIL CONTRACT
- Any non-zero exit code.
- Malformed `artifact.json` or missing required fields.
- Hung process or timeout requiring manual SIGKILL.
