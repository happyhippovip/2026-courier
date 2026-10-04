# WP003: Missing PyYAML Dependency in Virtual Environment

## Target
`requirements.txt` (or equivalent dependency file)
`tests/test_ci_acceptance_credentials.py`

## Defect
The Windows test run fails to collect `tests/test_ci_acceptance_credentials.py` due to a missing dependency (`ModuleNotFoundError: No module named 'yaml'`).

## Instructions for SOLE_WINDOWS_WRITER
1. Add `pyyaml` to the project's dependency definition (`requirements.txt`, `pyproject.toml`, or similar).
2. Install the missing dependency in the `.venv`.
3. Verify that the `ModuleNotFoundError` is resolved when running `python -m pytest tests/test_ci_acceptance_credentials.py`.

## Causal Path
The environment configuration used by the worker nodes is missing `pyyaml`, causing test collection to fail before test execution even begins.
