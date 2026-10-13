# Canonical Handoff — L3-RUNONCE-CLAIM-HARDEN (2026-10-07)

Workkey: L3-RUNONCE-CLAIM-HARDEN (lane L3, files: courier_worker/host.py, tests/test_l3_worker_host.py)
Writer: Muse session 01a1180e-fc11-7600-aee5-5bfb60965e39 (shell-less: PowerShell sandbox setup failed 2x, same infra error)

## Terminal flags (docs/CANONICAL_COMPLETION_HANDOFF.md)

- GOAL_SATISFIED: NO (fix + 2 tests written and reviewed; not executed, not committed)
- REGRESSION_PASS: NO (no runner; shell sandbox down)
- PRODUCT_TESTS_PASS: NO (not run)
- COURIER_TESTS_PASS: NO (not run)
- SINGLE_WRITER_PRESERVED: YES (no other open PR touches run_once; verified below)
- HUMAN_GATE_REQUIRED: YES (commit/push/PR/test need a shell-capable session or Dennis)
- ACTIVE_WORK_AT_END: uncommitted edits in courier_worker/host.py + tests/test_l3_worker_host.py
- UNRESOLVED_BLOCKER: shell unavailable — `muse.powershell` fails in sandbox setup
  (`admit deny-read state .../deny_read_acl_state.json`), 2 identical probes, no repair attempted
- MANUAL_STATE_SURGERY_USED: NO
- DIRECT_BYPASS_USED: NO
- READY_FOR_NEXT_GOAL: NO (blocked on test-run + commit first)

## Reconciliation evidence (fresh, shell-less via GitHub API + local .git reads)

- origin/integration/v1 = b9fc486a (2026-10-07T17:41Z, "record PR #121 and #131 merge status")
- local refs/heads/integration/v1 = 4b0eed7d (STALE), HEAD = refs/heads/lane/L1-integration @ 330f5f01
- Defect REVERIFIED at origin HEAD: raw host.py from integration/v1 lines 805-807 show
  spawn -> _active set -> _write_claim_record OUTSIDE try (identical to local checkout).
- Open PRs: 20. L3-adjacent: #139 (lane/L3-thermal-relief, thermal pauses), #141 (local_shell
  allowlist), #151 (thermal iterate fix, stacked on #139, touches service.py + appends tests
  at tests/test_l3_worker_host.py ~L594/~L750). Collision check: run_once on #139's branch is
  byte-identical in the claim region (no overlap); no open PR mentions run_once/claim-record;
  my tests sit at ~L150, far from #151's hunks. Workkey is DISTINCT and FREE.
- Issue #54 newest rules honored: 2026-10-06 HOST-PRESSURE OVERRIDE (no local wall/file claim
  tasks, ownership = GitHub PR/lane record, smallest targeted test only, CI owns broad suites)
  and 2026-10-07 no-grep-family rule (used direct reads + GitHub APIs; muse.search only).

## Change (minimal, L3-owned)

courier_worker/host.py run_once: claim-write failure after spawn previously leaked the live
child tree (no record => orphan gate blind) and left _active set (HostBusy forever).
Now: claim write is guarded; on failure the owned tree is terminated and the host released
(original error re-raised). If cleanup itself is unproven, ContainmentError is raised and the
host stays wedged (fail closed) — mirrors the existing finally (release only after cleanup).

tests/test_l3_worker_host.py (+2, beside test_second_claim_while_busy_is_refused):
- test_claim_write_failure_kills_tree_and_releases_host: OSError from claim write =>
  original error, busy False, child dead (H._owner_alive), no claim file, host reusable.
- test_claim_write_failure_with_unproven_cleanup_wedges_host: terminate mocked to fail =>
  ContainmentError("unproven"), busy stays True, next run_once => HostBusy.

Note: working-tree .py files are CRLF (no .gitattributes); inserted lines are LF.
Functionally irrelevant (no CI ending gate); normalizes on commit with autocrlf.

## NEXT_SAFE_ACTION (first shell-capable session; do NOT restack more work first)

1. `git status --short` (expect only the 2 files above + this checkpoint)
2. `python -m pytest tests/test_l3_worker_host.py -k claim_write_failure -q`
3. `python -m pytest tests/test_l3_worker_host.py -q` (lane module gate)
4. `git add courier_worker/host.py tests/test_l3_worker_host.py docs/v1/L3-RUNONCE-CLAIM-HARDEN_CHECKPOINT_2026-10-07.md`
5. Commit on a lane branch from CURRENT origin/integration/v1 (rebase first; local is stale),
   push, open PR against integration/v1, title: `fix(l3): harden run_once against claim-write failure`
6. Then REFETCH and continue the writer loop with the next free workkey.

TIMESTAMP_UTC: 2026-10-07 (evening run)
CURRENT_GOAL: L3 run_once claim-write hardening committed + PR open
ENDING_FINGERPRINT: host.py run_once guarded claim write + 2 tests, uncommitted, shell down
