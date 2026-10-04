# Scope
`scripts/invoice_generator.py`

# Existing tests inspected
No existing tests were present. Code coverage was at 36%.

# Commands executed
- `pytest tests/ -k invoice_generator --cov=scripts.invoice_generator --cov-report=term-missing` (initial check)
- `pytest tests/test_invoice_generator.py --cov=scripts.invoice_generator --cov-report=term-missing` (test run)
- `coverage report -m` (final coverage verification)

# Passing checks
All 4 newly added tests pass successfully:
- `test_invoice_generator_setup`
- `test_generate_invoice_defaults`
- `test_generate_invoice_sequence`
- `test_main_execution`

# Failing checks
None (ignoring the documented, OS-specific `pytest` teardown `PermissionError`).

# Audit findings confirmed
No specific prior audit findings applied to this module.

# Audit findings disproved
N/A

# Missing tests
None. All logic is now covered.

# Edge cases
- Missing fields in `experiment_data`: Covered via defaulting logic.
- Sequence incrementation per prospect alias: Covered and correctly formats incrementing sequence padding to `02d`.
- Creation of `INVOICE_DIR` using `mkdir(parents=True, exist_ok=True)`: Handled automatically on `generate_invoice()`.

# Recommended implementation fixes
None required. The code correctly handles arbitrary experiment data dictionaries, successfully generating correctly formatted and indexed UUID-based payment references.

# Suggested next verification scope
`scripts/poison_test.py` or another remaining unverified script from the audit ledger.
