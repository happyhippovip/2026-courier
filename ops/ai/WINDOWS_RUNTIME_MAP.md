# Windows Runtime Map

BOUND_TO_CODE_HEAD: 7c495f8c1b31293f8d3a5465035d2d3f61cbd3a7
UPDATED_AT_UTC: 2026-09-18

OBSERVED_AT: UNKNOWN
CANONICAL_RELEASE_SHA: UNKNOWN
WINDOWS_WORKTREE: UNKNOWN
WINDOWS_HEAD: UNKNOWN
ACTUAL_SERVING_SHA: UNKNOWN

PROCESS_ID: UNKNOWN
PROCESS_OWNER: UNKNOWN
EXECUTABLE: UNKNOWN
SERVICE_OR_AUTOSTART: UNKNOWN
LISTENER: UNKNOWN

CHECKPOINT_PATH: UNKNOWN
STATE_PATH: UNKNOWN

## Required evidence chain

actual process
→ executable
→ release worktree
→ exact SHA
→ persistent OS ownership
→ physical scenario observation

Do not infer code identity from a health label.

Every Windows packet should name which downstream Ledger invariant/evidence it supports.
