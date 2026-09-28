# Family 9: Wall Reliability Audit & Mechanics

**Status**: VERIFIED  
**Goal**: `MANY_WINDOWS WITHOUT MANY_DUPLICATE_JOBS`

---

## 1. Wall Reliability Mechanics Audit

### A. One-Prompt Role Selection & Claim Collision Prevention
- **Mechanism**: Atomic file reservation in `ops/ai/wall_claims/{SLOT}.claim.json` using exclusive write creation.
- **Invariant**: If slot file exists or is flagged `CLAIMED`, subsequent workers immediately advance to the next index (`MAC-SLEEP-001` -> `002` -> `...` -> `050`).
- **Proof**: 5 concurrent worker claims recorded without collision (`MAC-SLEEP-001..004`, `MAC-MEGA-001`).

### B. Completed-Task Persistence & Deduplication
- **Mechanism**: Every completed package is checkpointed to `ops/ai/wall_results/{TASK_ID}_result.md` and appended atomically to `ops/ai/wall_ledger/ledger.jsonl`.
- **Deduplication Key**: `FINGERPRINT` string (e.g. `SHA256_FINGERPRINT_{TASK_ID}`) ensures replay or re-investigation is skipped (`RESULT_REUSE_FIRST=YES`).

### C. Stale Lease Handling
- **Mechanism**: Server-side threshold of 300 seconds (`now - last_seen > 300`).
- **Behavior**: `/tasks/reclaim_stale` quarantines dispatched tasks into `HUMAN_REQUIRED` with reason `STALE_WORKER_EFFECT_AMBIGUOUS`. Does not blindly release back to queue.

### D. Session & Continuity (/clear, Provider Change)
- **Invariant**: `SESSION_MEMORY_IS_CACHE. REPO_LEDGER_IS_DURABLE_TRUTH.`
- **Continuity**: When context clears or a new Google account logs in, the worker reads `WALL_QUEUE_CURRENT.md` and `ledger.jsonl`.
- **Zero Replay**: Completed tasks are never re-run due to session reset.

### E. TRUE_IDLE & Cost/Quota Stop
- **Mechanism**: When `CURRENT_UNWORKED_QUEUE_SIZE == 0` and all authorized lanes are covered, worker enters `TRUE_IDLE` with bounded sleep backoff (`sleep 900`).
- **Prevention**: Prevents recursive AI prompting, token burn, or speculative source crawling.
