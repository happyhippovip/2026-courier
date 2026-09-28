# Batch 28 Evidence - NO-OPUS FAST CONVERGENCE

## Substep 1: Deduplication & Classification
Analyzed findings from `MUSE_WHATS_LEFT_CURRENT.md`:
- **D1/D2 (Schema Drift adapter/intake)**: `MUST_FIX_BEFORE_CODEX`. The revenue worker adapter and the integration contract were stripping `result_data` which broke the revenue pipeline.
- **D3 (Verifier Capabilities)**: `DISPROVEN`. The planner (`revenue_customer_intake.py`) correctly sets `capabilities` on the task, making the branch reachable.
- **C (Error-Code Semantics)**: `C4_AMBIGUITY_OPTIONAL`. Minor 404 vs 400 discrepancy for unknown workers; fail-closed and non-critical.
- **A, E, I, L, W**: `DISPROVEN` (No issue found, intended behavior).

## Substep 2 & 3: Source-Grounded Fixes
- **Fix D1**: Edited `scripts/revenue_worker_adapter.py` to ensure `result_data` is preserved in `res_payload` and handles failures safely.
- **Fix D2**: Patched `scripts/integration_contract.py` (`validate_durable_result`) to explicitly permit `result_data` to pass through without being stripped.
- Tested changes successfully against existing tests.
