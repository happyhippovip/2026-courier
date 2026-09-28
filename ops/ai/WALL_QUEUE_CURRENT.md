# Wall Queue Current — 2026-09-28

## Phase
PRE_CODEX_STATE=DURABILITY_PENDING
HARD_NO_IDLE=ACTIVE
MAC_FINISH24=COMPLETED

## Task Families
- **MAC-HNI (Hard No Idle)**: 1-22 COMPLETED. MAC_HNI_16 pending exact FINAL_SHA binding.
- **MAC-FINISH24**: 1-24 COMPLETED (RECONCILED).

## Directives
- **LEDGER_WORK**: SKIP (100% reconciled)
- **GATE**: Blocked by PRE_CODEX Windows durability.
- **MAC-HNI**: Blocked.
- **NEXT TARGET**: Continuous polling until PRE_CODEX becomes READY. Relaunched agy daemon to check continuously.
