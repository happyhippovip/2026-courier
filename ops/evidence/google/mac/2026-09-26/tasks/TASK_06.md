# TASK_06: Compare Muse CLI with Courier Adapter Expectations

STATUS=DONE
NEW_EVIDENCE=scripts/muse_wall_supervisor.py audit: 1. Passes --reasoning-effort auto (crashes with exit code 2). 2. Calls muse resume session-SLOT-01-... without passing --session-id <UUID> at exec time (fails exit code 1). 3. Calls muse session-message --workspace ... which fails syntax check.
PROVEN=3 critical CLI syntax defects exist in scripts/muse_wall_supervisor.py (M45-MUSE-CLI-REASONING-EFFORT-01, M45-MUSE-CLI-SESSION-REF-01, M45-MUSE-CLI-SESSION-MESSAGE-SYNTAX-MISMATCH-01).
UNKNOWN=None
BLOCKER=WAIT_FOR_WRITER (Source edits restricted to Windows / MAC-01).
NEXT=TASK_07
