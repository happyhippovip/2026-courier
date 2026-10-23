#!/bin/bash
S=/tmp/claude-0/-home-user-2026-courier/4510bb24-32c0-5203-8ebf-43dd2db70f44/scratchpad
declare -A T
T[F-C1_L2_controller_cost_admission.diff]="tests/controller/test_ctrl_cost_admission.py tests/controller/test_ctrl_service.py tests/controller/test_ctrl_golden_contract.py tests/controller/test_ctrl_moat_hardening.py"
T[WQ-1b_lease_recovery.diff]="tests/test_queue_lease_recovery.py tests/test_queue_feed_foreign_lease.py tests/test_queue_feed_crash_points.py tests/test_work_queue.py tests/test_ledger_tick.py"
T[H12_local_shell_env_allowlist.diff]="tests/test_local_shell_env_allowlist.py tests/test_local_shell_adapter.py"
T[WIN-COST-1_included_quota_unknown.diff]="tests/test_windows_costgate_and_writer_lease.py"
T[VC-1_verified_continuation_claim_safety.diff]="tests/test_verified_continuation_claim_safety.py tests/test_verified_continuation.py"
T[VC-1_on_826_verified_continuation.diff]="tests/test_verified_continuation_claim_safety.py tests/test_verified_continuation.py"
T[CDX-COST-1_codex_bridge_costgate.diff]="tests/test_run_codex_bridge_costgate.py tests/test_run_codex_bridge.py"
T[PE-1_provider_exec_overflow.diff]="tests/test_provider_exec_cost_overflow.py"
ref=${1:-origin/integration/v1}
for p in "${!T[@]}"; do
  rm -rf $S/mx; git -C /home/user/2026-courier worktree prune
  git -C /home/user/2026-courier worktree add -q --detach $S/mx $ref 2>/dev/null
  cd $S/mx
  out=$(git apply --3way $S/$p 2>&1); rc=$?
  if git diff --name-only --diff-filter=U | grep -q .; then r="CONFLICT $(git diff --name-only --diff-filter=U | tr '\n' ' ')";
  elif [ $rc -ne 0 ]; then r="APPLY_FAIL $(echo "$out" | grep -m1 error)";
  else r=$(timeout 600 ../venv/bin/python -m pytest -q -p no:cacheprovider ${T[$p]} 2>&1 | tail -1); fi
  echo "$p | $r"
  cd $S; git -C /home/user/2026-courier worktree remove --force $S/mx
done
