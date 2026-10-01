# INCIDENT — foreign branch switch mid-session (read-only record, no action taken)

Slot MUSE-45, COURIER_LIVE_SHOW_CONTINUE, observed 2026-09-26 (after T-K, before T-L).

## What happened (OBSERVED)

- Mid-session, all TRACKED files I had been reading vanished from the worktree:
  scripts/agent_handoff_ledger.py, scripts/courier_continue.py,
  scripts/run_chief_commander.py, ops/ai/*.yaml + *.md (tracked), AGENTS.md,
  docs/RELEASE_CANDIDATE.md, scripts/windows_muse_wall/*, most tests/*,
  most server/*.
- UNTRACKED files survive: runtime/** (all slot states, jobs, logs, my claim),
  ops/ai/packets/MUSE45_* (my 11 packets), runtime/slots/MUSE-45/* (35-file corpus).
- `.git/HEAD` now reads `ref: refs/heads/fix-cb1-new`;
  `.git/refs/heads/fix-cb1-new` = 329abd8077a9f53ecd34eb3bee5d506735d06dbe.
  (Prior branch per Google checkpoint: ledger-reconciliation-final @ 27b22d7e;
  per T22: HEAD=b927f106. I never read HEAD before the switch.)
- New tree has a DIFFERENT suite: tests/ without ledger/motor/wall tests,
  server/ reduced to app.py + logs, docs/ product-strategy set, mac_worker/
  with muse_adapter/muse_supervisor/runtime_state (unseen lineage),
  windows_worker/ WITHOUT run_loop.bat/stop_safe.py/worker_status.py/start.py.
- Cause (INFERRED, not proven): a foreign branch switch (checkout fix-cb1-new)
  by another live actor (5 WIN workers + Google active; operator possible).
  NOT caused by me: zero shell, zero git, reads + slot/packet writes only.

## Impact on MUSE-45 evidence

- My packets T-A..T-K + DEDUPE + all slot-corpus reports are bound to the
  PRE-SWITCH tree. File:line pins in them do NOT resolve on fix-cb1-new.
  They stand as point-in-time evidence; NOT rewritten (history preserved).
- runtime/ proof (16 DONE jobs/logs) SURVIVES on disk (untracked).
- Findings citing surviving files keep standing (to be re-verified per file);
  findings citing vanished files are VACATED on this branch (branch-scoped).

## Response (this session)

- NO switch-back, NO checkout, NO merge, NO disturbance of the switcher
  (mission no-checkout rule binds me; reverting would collide with live actors).
- Work CONTINUES on the new tree: T-L pivots to (1) survival re-verify of
  portable findings, (2) fix-cb1-new inventory (read-only), (3) runtime proof
  custody (untracked, intact). Shell still DOWN; still LIGHT-only.
- Flag for owner/operator: a shared-checkout branch switch invalidates every
  live agent's tracked-file evidence at once. If unintentional, re-announce;
  if intentional pivot, broadcast new branch + HEAD so agents rebind.
