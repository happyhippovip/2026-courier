# T26 RESULT — Dispatcher/validator coverage spot + G-5 re-check (read-only)

MODE: shell-less LIGHT. No test runs; reference + pin checks only.

## 1. Dispatcher "13 tests" pin — CORROBORATED EXACTLY
- tests/test_github_dispatcher.py contains exactly 13 `def test*` functions
  (counted this session). Names cover the guarded families from
  DISPATCHER_guards.md: single-flight reentry, bounded recovery (x2),
  reap/cleanup, path confinement, dispatch-identity requirement, atomic
  materialize, conflict-never-replaces, concurrent-idempotent, restart
  resume/posted-cleanup/multi-fail/corrupt-fail.
- Plus: direct module import (line 7) + contract-path reference in
  test_server_integration_contract.py. Dispatcher = DIRECT-tested. No gap.

## 2. G-5 bare-python3 adapter spawn — STILL OPEN (RE-CONFIRMED)
- scripts/courier_github_dispatcher.py:29 (OBSERVED):
  `python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"`
- No sys.executable migration. Windows acceptance-path bite stands.
  Service/dispatcher-owner scope; no touch here.

## 3. Verifier coverage shape — SUBPROCESS-ONLY (gap stands)
- scripts/courier_verifier.py: launched via subprocess in
  test_auto_replenishment.py:35 + test_tomato_two_torture.py:104, path-
  referenced in test_server_integration_contract.py:93. Zero direct-import
  test files. Consistent with T10's "SUBPROCESS 1 (verifier)" label.
  Failure modes inside verifier mains are exercised only end-to-end.

## 4. validate_durable_result — DIRECT-covered (no gap)
- Direct imports + assertions in test_github_worker_adapter.py and
  test_result_identity_binding.py. OK.
