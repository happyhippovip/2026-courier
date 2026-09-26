# TASK_06 — Muse CLI vs Courier Adapter Comparison

STATUS=DONE
NEW_EVIDENCE=CONFIRMED

## Comparison Matrix: Muse CLI vs Courier Adapter Expectations

| Dimension           | Muse CLI Actual (v1.4.0)          | Adapter (muse_wall_supervisor.py)   | Match? |
|---------------------|-----------------------------------|-------------------------------------|--------|
| Binary name         | muse                              | "muse"                              | YES    |
| Subcommand          | exec                              | "exec"                              | YES    |
| --workspace         | Supported, required for confinement| Passes self.workspace              | YES    |
| --reasoning-effort  | none|minimal|low|medium|high|xhigh|max|ultra | "auto" (default) | **NO — BUG** |
| --yolo              | Supported                         | Appended when yolo=True             | YES    |
| Headless mode       | --json for JSONL output           | Not used                            | PARTIAL |
| Session resume      | muse resume <session-ref>         | self.resume_session()               | YES    |
| Session message     | muse session-message              | self.send_message()                 | YES    |

## Mismatch Classification
CRITICAL_MISMATCH=reasoning_effort="auto" → M45-MUSE-CLI-ARG-01 → exit code 2 → supervisor crash loop
NON_CRITICAL=--json flag not used (stdout not machine-parsed; acceptable for Canary 1)

## Canary 1 Path
For Canary 1 isolation proof, adapter mismatch can be bypassed:
- Call `muse exec --workspace /canary/workspace --reasoning-effort high --yolo` directly
- No supervisor invocation needed; Mac Worker daemon handles claim/result independently

PROVEN=Adapter mismatch identified and classified. Only reasoning_effort is critical. All other flags match.
UNKNOWN=None
BLOCKER=Adapter bug — fix required for supervisor path, not for direct-exec Canary 1
NEXT=TASK_07
