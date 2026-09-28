# Hard No-Idle 50 Prompt Pack Usage Guide — 2026-09-28

Status: CANONICAL USAGE PROTOCOL
Target Audience: Multi-window orchestrators, autonomous loop relaunchers, background task swarms.

## Operational Command
To execute any prompt from the pack:
```bash
agy -p "$(cat ops/ai/hard_no_idle50/HNI_01_RUNTIME_INVARIANT_AUDIT.txt)" --disable-slash-commands --dangerously-skip-permissions
```

## Continuous Worker Loop
Workers should iterate sequentially through HNI_01 to HNI_50 or draw claims atomically using `ops/ai/wall_claims/`.
When all tasks in the current batch complete:
1. Recompute next ready tasks from `ops/ai/GOOGLE_MAC_PHYSICAL_PROOF_PREP_QUEUE_M181_M260_2026-09-28.md`.
2. Re-harvest and reconcile ledger entries in `ops/ai/wall_ledger/ledger.db`.
3. Verify zero lingering unpersisted claims.
