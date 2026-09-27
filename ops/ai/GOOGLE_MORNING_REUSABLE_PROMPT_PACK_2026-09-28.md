# Google Morning Reusable Prompt Pack — 2026-09-28

Use these repeatedly in free Google CLI windows. Claims/results remain durable; new sessions do not reset completion.

## Windows
- ops/ai/GOOGLE_WINDOWS_100X_UNIVERSAL_WORKER_PROMPT.txt
- ops/ai/GOOGLE_WINDOWS_LEDGER_REPLAY_100X_PROMPT.txt
- ops/ai/GOOGLE_WINDOWS_TEST_MATRIX_100X_PROMPT.txt
- ops/ai/GOOGLE_WINDOWS_GATE_CONTRADICTION_100X_PROMPT.txt

## Mac
- ops/ai/GOOGLE_MAC_100X_UNIVERSAL_WORKER_PROMPT.txt
- ops/ai/GOOGLE_MAC_RUN_PREP_100X_PROMPT.txt
- ops/ai/GOOGLE_MAC_RESTART_PROOF_100X_PROMPT.txt
- ops/ai/GOOGLE_MAC_CORE_FREEZE_100X_PROMPT.txt

## Distribution guidance
Windows 20 free windows:
- 8 universal
- 4 ledger/replay
- 4 test matrix
- 4 gate/contradiction

Mac 16 free windows:
- 6 universal
- 4 run prep
- 3 restart proof
- 3 core-freeze proof

Do not treat these counts as heavy-job counts. MAX_HEAVY_JOBS=1 per host.
If workers repeatedly return TRUE_IDLE after one bounded refresh, stop opening more windows until a gate/state change unlocks real work.
