# Wall Queue Current

Status: STABLE POINTER

WALL_SYSTEM=ops/ai/WALL_SYSTEM.md
TASK_SCHEMA=ops/ai/WALL_TASK_PACKET_SCHEMA.md
MASTER_PROMPT=ops/ai/UNIVERSAL_MD_WALL_MASTER_PROMPT.txt
MAC_PERMANENT_WORKER=ops/ai/MAC_GOOGLE_PERMANENT_WORKER_PROMPT.txt

CURRENT_PREPARATION_PACK=ops/ai/GOOGLE_LEDGER_MUSE_WALL_BUILD_PACK_2026-09-27.md
CURRENT_GOOGLE_QUEUE=ops/ai/GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md

CURRENT_WALL_BUILD_QUEUE=ops/ai/WALL_BUILD_QUEUE_V1.md
CURRENT_WALL_BUILD_PROMPT=ops/ai/GOOGLE_WALL_SYSTEM_BUILDER_MASTER_PROMPT.txt
OPERATOR_PROTOCOL=ops/ai/WALL_ROLLOUT_AND_OPERATOR_PROTOCOL.md

CURRENT_GOAL:
Finish Extended Execution Ledger, cost-aware wall preparation, automatic result harvesting, and reusable Muse wall bootstrap.

QUEUE_REFRESH_RULE:
Use durable result summaries and canonical truth only.
Do not broad-scan source to invent new work.

SOURCE_WRITER:
Windows Antigravity Central Writer remains the only final-candidate application source writer unless newer canonical truth explicitly changes this.

WHEN CURRENT QUEUES COMPLETE:
One PREPARER generates the next Markdown queue generation from:
1. current canonical truth;
2. completed result summaries;
3. explicit Central Writer handoff;
4. open Ledger blockers.

If those sources define no concrete READY work, wall becomes IDLE.
