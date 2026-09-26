# Legacy Mac Pool Writer Quarantine — 2026-09-27

Status: ACTIVE COORDINATION WARNING

## Why

A legacy Mac Google/Antigravity pool prompt (MISSION=COURIER_MAC_POOL_12_NONINTERFERENCE) allowed MAC-01..06 to attempt a Mac writer lock and, when acquired, mutate an isolated writer worktree.

That behavior conflicts with the current canonical endgame authority:

- Windows Antigravity Central Writer is the ONLY source writer for the final canonical candidate.
- Final candidate scope is exactly five authorized files.
- Mac lanes are physical-proof / read-only support unless explicitly reassigned by current durable coordination.

## Observed legacy side work

A Mac pool session reported acquiring a Mac writer lock and producing a series of local commits across many unrelated files, including resource policy, Mac worker/runtime, dispatcher, verifier safety, publishing, invoice logic, and tests.

Those changes may contain useful ideas, but they are NONCANONICAL SIDE WORK for the current final-candidate path.

Do not merge/cherry-pick them into the final candidate automatically.

Any useful change must be harvested later as an independently reviewed backlog item after the current five-file final candidate + RUN_1/RUN_2 path is complete, unless the Chief explicitly re-prioritizes it.

## Hard rule

DO NOT USE legacy prompt behavior that lets a Mac pool slot become source writer during the current endgame.

Current Mac/Google/Muse overnight prompts are READ_ONLY_REPORT by default.

If an old session still holds a Mac writer lock:
- do not create a second writer;
- checkpoint its state;
- stop source mutation;
- release/retire the legacy writer path safely when practical;
- preserve commits/evidence for later harvest;
- continue read-only work.

## Current canonical state

Accepted base:
candidate-b-1
4c1e24ccc522042af826bc4c2b595daf85d097f9

Rejected:
candidate-b-2
83940de3d7d33776a712e7506aa76726d16f8587

Final candidate still requires the exact five-file correction + targeted evidence before Codex High and Mac physical RUN_1.

## Never confuse

SIDE_BRANCH_GREEN_TESTS != FINAL_CANONICAL_CANDIDATE

LOCAL_MAC_COMMIT != AUTHORIZED_FINAL_DELTA

READ_ONLY_AUDIT_FINDING != MERGE_PERMISSION
