# Scope
scripts/run_demo_workflow.py

# Existing tests inspected
None existed. Created `tests/test_run_demo_workflow.py`.

# Commands executed
- `list_dir scripts` (to find next candidate since `dispatch_worker.py` doesn't exist)
- `view_file memory/WINDOWS_VERIFICATION_LEDGER.md`
- `view_file scripts/run_demo_workflow.py`
- `write_to_file tests/test_run_demo_workflow.py`
- `.venv\Scripts\python -m pytest tests/test_run_demo_workflow.py --cov=scripts.run_demo_workflow --cov-report=term-missing`

# Passing checks
5/5 tests pass successfully.
Coverage achieved: 99% (Misses only `if __name__ == "__main__": sys.exit(main())`).
- Verified `reset_demo_environment` function correctly clears and creates demo evidence subdirectories.
- Verified `run_live_demo` runs through the full execution logic, handles mocked agent responses, asserts `BLOCKED_HUMAN_GATE` for the initial phase, and `COMPLETED` for the resume phase.
- Verified correct parsing of argparse arguments in `main()`.
- Verified copying dummy files into the demo evidence directory logic.

# Failing checks
None.

# Audit findings confirmed
N/A

# Audit findings disproved
N/A

# Missing tests
None remaining. CLI arguments, environment resets, successful execution, and failure bubbling are covered via mocks.

# Edge cases
- If `shutil.copy` cannot find files in `events/dispatch` or `events/processed` (which can happen during mocked runs), the script safely uses `if src_file.exists():` before attempting to copy.
- Argument `--reset` successfully overrides previous demo instances by removing the whole tree.

# Recommended implementation fixes
None required. Script is perfectly functional.

# Suggested next verification scope
`scripts/validate_chief_relay.py` or `scripts/validate_courier_task.py`
