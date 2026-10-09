# WIN Acceptance GAP 2 — restart -> worker reconnect / live agent (Rule 0 steps 8-10)

Date: 2026-10-07. Worker: Windows clean-machine acceptance (shell-less session).
HEAD verified: `integration/v1` = `b9fc486a` (2026-10-07T17:41:13Z).
All file facts below observed via raw read at that HEAD, not inferred.

## Chain legs

restart -> reconnect / live agent -> job execution after restart.

## Finding (observed)

`tests/test_win_clean_machine_harness.py` at HEAD proves after restart:
- Hub serves `/hub/api/home` with the previously done tasks (lines ~222-229).
- PR #157 (open) adds replay/rebuild-hash equality (Rule 0 step 10).

What NOBODY proves (current file, restart section, lines ~231-232):

    # Check that no worker lock exists from old process, wait for worker to boot up
    time.sleep(2)

The comment promises a lock check; the code only sleeps. Zero assertions that:
1. a worker process re-registers with the controller after restart
   (no stale `current_task`, no WORKER_BUSY zombie, no lock leftover);
2. the reconnected worker can claim AND execute a NEW synthetic task
   post-restart (live agent, not just persisted history);
3. exactly one worker generation is active (old generation provably gone,
   new generation provably the claimant — dispatch fencing across restart).

Related but distinct active scopes (not this gap):
- #159 fences uncertain cleanup before successor launch (runtime code).
- #156 fail-closed `run_once` on claim-write failure (L3 runtime code).
- #157 owns the harness test FILE (orphan + replay + uninstall-parse).
  This gap is the missing reconnect/live-agent ASSERTION SET, to be added
  by L1 after #157 lands. No edit to that file is made here.

## Why this scope is free

Same ownership check as GAP 1 (open PRs exactly #132-#159): no PR asserts
post-restart worker reconnect + post-restart execution in the
clean-machine lifecycle. #152 covers local_shell E2E on the golden path,
not the Windows restart/reconnect leg.

## Live-evidence status

BLOCKED in this session: shell sandbox setup fails, no local execution.
NOT claimed as proven. Runbook below produces the evidence on a
shell-capable Windows host.

## Runbook (shell-capable Windows host, repo at integration/v1)

Extend the existing harness flow (do not fork it): after the current
restart + Hub-home assertions:

1. Poll controller for worker registration: expect a NEW worker id or
   generation marker distinct from the pre-close worker pid; record
   pre-close pids vs post-restart pids (no pid reuse confusion: compare
   pid + process start time).
2. Submit one NEW synthetic task post-restart via the same `api()` helper;
   wait for COMPLETE with the existing `wait_for` (30s budget).
3. Assert the claimant worker pid belongs to the post-restart generation.
4. Assert no pre-close worker/controller/hub pid survives
   (complement to #157's orphan assert, keyed on generation).
5. Negative: while the post-restart worker holds the task, a second
   worker start must NOT double-claim (WORKER_BUSY or clean standby,
   never two executors of one dispatch).

## Pass criteria (for the owning lane, suggested L1 post-#157)

- FAIL today (predicted): steps 1-5 have no assertions; at minimum the
  lock-check comment is uncovered.
- Fixed state: the clean-machine run proves restart -> worker
  re-registration -> new task claimed by the new generation -> COMPLETE
  exactly once, with old-generation pids provably gone.

## Queued next (GAP 3 candidate, not started)

Real `install.ps1` -> first launch -> real `uninstall.ps1` lifecycle:
install.ps1 is machine-wide ProgramFiles + SYSTEM task (vs V1 per-user
baseline), uses blocking `Read-Host`, defaults to a LAN server URL,
stores the token with no ACL; uninstall.ps1 is admin-only, hardcodes
`C:\Users`, and offers no `-RemoveUserData` opt-in although Rule 0
step 12 allows removal on explicit user choice. Free as of this check;
needs re-verification before claiming (ownership can shift fast).
