# Wall Queue Current

Status: ACTIVE POST-LEDGER POINTER
Updated: 2026-09-28

LEDGER_STATUS=COMPLETE
LEDGER_ROUTING=DISABLED_UNLESS_RETEST_TRIGGER

ACTIVE_GOOGLE_EXECUTION_MODE=DIRECT_IDE_LOCAL
ACTIVE_GOOGLE_QUEUE=ops/ai/GOOGLE_IDE_DIRECT_50_QUEUE_2026-09-28.md
ACTIVE_GOOGLE_PROGRESS=ops/ai/GOOGLE_IDE_DIRECT_50_PROGRESS.md
ACTIVE_GOOGLE_WORKER=ops/ai/GOOGLE_IDE_DIRECT_50_WORKER_PROMPT.txt

ACTIVE_MUSE_PACK=ops/ai/AGGRESSIVE_MUSE_GOOGLE_WINDOW_PACK_2026-09-28.md
ACTIVE_MUSE_DIR=ops/ai/muse_aggressive20
ACTIVE_WINDOWS_GOOGLE_BATCH_DIR=ops/ai/google_windows_batches

WALL_SYSTEM=ops/ai/WALL_SYSTEM.md
WORKING_ONLY_POLICY=ops/ai/WORKING_ONLY_EXECUTION_POLICY_2026-09-28.md
GATE_STATE_CURRENT=ops/ai/GATE_STATE_CURRENT.md
MODEL_CAPABILITY_REGISTRY=ops/ai/COURIER_MODEL_CAPABILITY_REGISTRY_2026-09-28.md
MODEL_ROUTING_POLICY=ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md
PROVIDER_LIMIT_POLICY=ops/ai/PROVIDER_LIMIT_AND_HUMAN_GATE_POLICY_2026-09-28.md

PERMANENT_MASTER_PROMPT=ops/ai/COURIER_PERMANENT_MASTER_WORKER_PROMPT.txt
LIVE_STATUS_CURRENT=ops/ai/LIVE_STATUS_CURRENT.md

CURRENT_GOAL:
Advance the post-Ledger critical path:
1 PRE_CODEX durability
2 PRE_CODEX handoff
3 CODEX_HIGH_ONCE
4 EXACT_MAC_BINDING
5 RUN_1_A_VERIFY_B_ZERO_RELAY
6 RUN_2_RESTART_NO_A_REPLAY
7 CORE_FREEZE
8 MINIMUM_REAL_PILOT
9 PRODUCT_SHELL_AFTER_POSITIVE_PILOT_SIGNAL

SOURCE_AUTHORITY:
Windows Antigravity Central Writer remains final-candidate application source writer unless newer durable truth explicitly changes ownership.
Mac physical runner owns RUN_1/RUN_2 only after gates open.
Codex runs exactly once per fixed gate fingerprint after authoritative PRE_CODEX READY.

ACTIVE ROUTING RULES:
- Do not route Ledger work unless a concrete durable RETEST_TRIGGER reopens it.
- Do not read legacy Ledger queues to look for work.
- Do not revalidate unchanged PRE_CODEX evidence.
- Exactly one PRE_CODEX durability owner.
- Google direct IDE work continues through local tasks even if remote Git is unavailable.
- Broken optional external paths are disabled, not repaired repeatedly.
- One finished task is not session completion.
- Physical RUN_1/RUN_2 stay Mac-owned.
- Product Shell remains blocked until positive real-pilot evidence.

WHEN CURRENT GOOGLE QUEUE COMPLETES:
1 update LIVE_STATUS_CURRENT.md;
2 synthesize earliest unfinished critical-path item;
3 generate only concrete post-Ledger follow-up work;
4 never fall back to archived Ledger queues.

LEGACY POINTERS:
Historical pointer snapshot moved to:
ops/ai/archive/WALL_QUEUE_LEGACY_POINTERS_2026-09-28.md
Do not route from that file.

ACTIVE_MUSE_EXECUTION_MODE=DIRECT_LOCAL_WALL
CURRENT_MUSE_WALL=ops/ai/MUSE_DIRECT_64_WALL_2026-09-28.md
CURRENT_MUSE_WORKER_PROMPT=ops/ai/MUSE_DIRECT_LOCAL_WALL_MASTER_PROMPT.txt
GOOGLE_WINDOWS_PULLTHROUGH_24=ops/ai/GOOGLE_WINDOWS_PULLTHROUGH_24_2026-09-28.md
GOOGLE_MAC_PREP_12=ops/ai/GOOGLE_MAC_PREP_12_2026-09-28.md
