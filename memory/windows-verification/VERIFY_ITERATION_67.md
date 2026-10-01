# VERIFY_ITERATION_67

## Component
`scripts/validate_courier_task.py`

## Date
2026-09-30

## Context
This script validates new incoming courier tasks before processing them. It verifies the schema version, envelope fields, route constraints, hash constraints, and ensures there is no existing terminal state for the task.

## Actions Taken
1. Added `tests/test_validate_courier_task.py`
2. Used `unittest.mock.patch` to inject mocked filesystem elements and arguments.
3. Created test coverage for:
   - Success path (valid task, outputting the path).
   - Invalid schema fields (missing `schema_version`).
   - Invalid version (1.0 vs 2.0).
   - Invalid type (RESULT instead of TASK).
   - Invalid route (wrong source).
   - Missing identity (`message_id` is null).
   - Parent ID constraint violation (`parent_id` is not null for a new TASK).
   - Iterations count mismatch (max_iterations != 1).
   - Payload hash mismatch (tampering check).
   - Unsupported result request.
   - Idempotency check against `processed_dir` containing the terminal record.

## Findings
- The script uses `raise SystemExit(...)` directly which was properly tested.
- 11/11 tests pass successfully.
- Code functions completely deterministic.

## Next Steps
Continue with iteration 68.
