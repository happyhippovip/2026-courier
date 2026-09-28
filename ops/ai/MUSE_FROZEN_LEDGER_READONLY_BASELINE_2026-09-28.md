# Muse Frozen-Ledger Read-Only Baseline — 2026-09-28

Purpose: make the closed Ledger useful to Muse without reopening it.

READ_ONCE:
- ops/ai/LEDGER_FREEZE_CURRENT.md
- ops/ai/GATE_STATE_CURRENT.md
- ops/ai/WALL_QUEUE_CURRENT.md

Muse may reuse:
- completion/coverage history;
- durable result fingerprints;
- do-not-repeat fingerprints;
- already reconciled task identities;
- prior evidence references that still match current source/runtime fingerprints.

Muse must independently source-check before relying on:
- state names/transitions;
- claim/lease/liveness semantics;
- current final SHA or PRE_CODEX readiness;
- source/build/runtime binding;
- RUN_1/RUN_2 execution truth;
- Core Freeze or pilot readiness.

Routing:
LEDGER -> FROZEN BASELINE
CURRENT MUSE WORK -> WHAT-IS-LEFT / CASCADE A -> B -> C
OPUS -> optional convergence accelerator
CODEX -> mandatory fixed-candidate HIGH once, only after authoritative PRE_CODEX READY
