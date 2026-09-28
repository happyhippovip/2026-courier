# MAC-FINISH-16 — RUN_2 Result Template

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-16
- **Area**: RUN2_RESULT_TEMPLATE
- **Status**: COMPLETE

Standardized result template for capturing physical RUN_2 restart telemetry and verdicts.

---

## 2. Template Structure
```markdown
# RUN_2 Restart Validation Result

- **EXECUTION_TIMESTAMP**: YYYY-MM-DDTHH:MM:SSZ
- **HOST**: macOS Darwin
- **CANDIDATE_SHA**: <FINAL_SHA>
- **CRASH_TIMESTAMP**: YYYY-MM-DDTHH:MM:SSZ
- **RESTART_TIMESTAMP**: YYYY-MM-DDTHH:MM:SSZ

### Restart Invariants
- `task_a_replayed`: FALSE
- `task_a_execution_count`: 1
- `state_restoration_latency_ms`: <MS>
- `task_b_dispatched_and_completed`: TRUE

### Overall Verdict
- **RESULT**: PASS
- **VERIFIER_SIGNATURE**: sha256-run2-restart-<HASH>
```
