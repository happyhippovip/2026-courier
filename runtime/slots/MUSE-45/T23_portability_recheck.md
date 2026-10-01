# T23 RESULT — Portability spot-check vs current tree (read-only)

MODE: shell-less LIGHT. Re-verifies T9/T11 portability pins. No test runs
possible (shell down); findings are path-literal facts, severity capped at LOW.

## 1. Thought tests still Mac-pinned — STILL OPEN (RE-CONFIRMED)
- tests/test_thought_ingestion.py:17:
  `MEMORY = Path("/Users/user/Downloads/2026-project-memory")`
- tests/test_thought_memory_mesh.py:16: same literal.
- Absolute Mac-only HOME path; nonexistent on Windows by construction. These
  tests cannot pass unmodified on this host (execution unconfirmed: no shell).

## 2. /tmp/ literals persist in tests — STILL OPEN (RE-CONFIRMED, LOW)
- 5+ files: test_auto_replenishment.py (mock/result paths),
  test_github_dispatcher.py (/tmp/task-1.json launch assertions),
  test_ledger_fix_guards.py (3 guard json paths), test_snitch_watchdog.py
  (audit string), test_worker_400_infinite_loop_attack.py (fake server path).
- On Windows Path("/tmp/x") resolves to <drive>:\tmp\x; mostly mock/assertion
  strings (harmless), but any real writes land outside the repo temp story.
  Owner call: tmp_path fixture migration. No edits made here.

## 3. /Users/user outside thought tests
- No other hits in tests/ for /Users/user|Darwin in this sample (15-cap search,
  2 hits total). T9's "agy /Users/user" lives outside tests/ (not re-checked).
