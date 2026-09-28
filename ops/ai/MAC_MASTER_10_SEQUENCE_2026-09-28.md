# Mac 10 Master Sequence — 2026-09-28

Status: AFTER LEDGER COMPLETE. Ledger stays closed unless RETEST_TRIGGER.
Current gate at creation: PRE_CODEX_STATE=DURABILITY_PENDING.

## Sequence
01. Pre-Codex Parallel Prep — 4 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_01_PRECODEX_PARALLEL_PREP_PROMPT.txt`
02. Exact Runtime Binding — 3 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_02_RUNTIME_BINDING_PROMPT.txt`
03. RUN_1 Proof Pack — 4 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_03_RUN1_PROOF_PACK_PROMPT.txt`
04. RUN_1 Physical Execution — 3 (1 runner + 2 support) logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_04_RUN1_EXECUTION_PROMPT.txt`
05. RUN_2 Restart / No-Replay Prep — 3 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_05_RUN2_RESTART_PREP_PROMPT.txt`
06. RUN_2 Physical Restart Proof — 3 (1 runner + 2 support) logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_06_RUN2_EXECUTION_PROMPT.txt`
07. Core Freeze Closure — 4 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_07_CORE_FREEZE_PROMPT.txt`
08. Minimum Real Pilot Readiness — 3 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_08_PILOT_READINESS_PROMPT.txt`
09. Pilot Execution + Evidence Review — 3 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_09_PILOT_EXECUTION_REVIEW_PROMPT.txt`
10. Product Shell + Release Readiness — 4 logical Mac/Google windows — `ops/ai/mac_master10/MAC_MASTER_10_PRODUCT_RELEASE_PROMPT.txt`

## Gate law
Masters 01-03 may do substantial candidate-independent work now.
Master 04 waits for READY_FOR_PHYSICAL_RUN=YES.
Master 06 waits for RUN_1 PASS.
Master 08 waits for Core Freeze.
Master 09 needs a real authorized pilot.
Master 10 needs durable positive pilot evidence.
MAX_HEAVY_JOBS=1 per Mac host.
