# Scope
scripts/validate_courier_task.py

# Existing tests inspected
None existed. Created `tests/test_validate_courier_task.py`.

# Commands executed
- `view_file scripts/validate_courier_task.py`
- `write_to_file tests/test_validate_courier_task.py`
- `.venv\Scripts\python -m pytest tests/test_validate_courier_task.py --cov=scripts.validate_courier_task --cov-report=term-missing`

# Passing checks
13/13 tests passed successfully.
Coverage achieved: 98%.
- Verified `TASK` payload schemas, rejecting invalid schemas.
- Verified missing envelope fields handling.
- Verified bad schema versions.
- Verified route checking (`github_courier -> codex`).
- Verified identity checks and specific values (`parent_id=None`, `max_iterations=1`).
- Verified `result_request` validation mapping.
- Verified payload hash checks.
- Verified strict deduplication rejecting duplicate files in `processed_dir`.

# Failing checks
None.

# Audit findings confirmed
N/A

# Audit findings disproved
N/A

# Missing tests
None remaining.

# Edge cases
- Missing parent directories or invalid JSON in search dirs during deduplication are safely ignored via `except (OSError, json.JSONDecodeError): continue`.
- Empty or string identity values caught cleanly with explicit type guarding.

# Recommended implementation fixes
None required.

# Suggested next verification scope
`scripts/publish_courier_result.py`
