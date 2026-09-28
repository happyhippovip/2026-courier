# MAC06 RUN_2 Restart — Controlled Restart Preparation

STATUS=PREPARED_NOT_EXECUTED
EXECUTION_GATE=CLOSED (RUN_1 physical PASS absent — see §8)
BASE=origin/candidate-b-1@4c1e24ccc522042af826bc4c2b595daf85d097f9
SESSION=cloud-octans (MUSE, MAC)
DATE=2026-09-28

All code refs below verified read-only against BASE via `git show`.
No process was stopped, started, or replayed. No source was edited.

## 1. Pre-stop checkpoint snapshot (to record at execution time)

Server side (single source of truth):
- Copy of STATE_FILE content + sha256, taken AFTER one final `save_state`.
- Per goal: `goal_id`, `current_step_index`, `status`.
- Per active task: `task_id`, `status`, `attempt_id`, `dispatch_id`,
  `worker_id`, `result_id` (if any), `resumed_from` (if any).

Mac worker side (`STATE_DIR`):
- `current_task.json` (persisted pre-exec in `run_muse`).
- `muse_process.json` (`state` must read CLEAN or ORPHANS_REMAIN — never
  trust a stale RUNNING after stop; re-verify post-start).
- `checkpoint*.json` files present (binding field noted).
- `muse.stdout` / `muse.stderr` tails (bounded evidence, not copied whole).

## 2. State persistence (verified, not assumed)

- `server/app.py:load_state/save_state`: JSON state, `save_state` writes
  `STATE_FILE.tmp` + `flush` + `os.fsync` + `os.replace` → atomic,
  crash-safe at file level.
- All mutating routes run under `STATE_LOCK` via `serialize_state_mutation`
  (`server/app.py:serialize_state_mutation`) — single-process safe.
- Mac daemon uses `atomic_json` for `muse_process.json`, `current_task.json`,
  quarantine checkpoints (`scripts/mac_worker/daemon.py:343,361,375`).
- Heartbeat every 30s during `run_muse` (`daemon.py:heartbeat_at`); absence
  of heartbeat is the liveness signal, not process-table guessing.
- `acquire_worker_lock`: one daemon per STATE_DIR — a second daemon would
  re-claim/re-send, so post-restart orphan check is mandatory
  (`require_no_orphan` before every `run_muse` exec).

## 3. Stop order (procedure — NOT executed)

1. Set STOP / block admission on workers first
   (`stopped() or not resource_ready()` raises `MuseAdmissionBlocked`
   before any new `Popen`).
2. Let any in-flight execution reach a boundary (process exit or
   timeout/output-limit raise → "reconcile, do not retry").
3. Verify `muse_process.json` leaves RUNNING state via the `finally:`
   `cleanup_group` path (`daemon.py:cleanup_group(proc, identity)`), which
   records CLEAN vs ORPHANS_REMAIN. If ORPHANS_REMAIN → no new execution
   allowed until orphans are reaped by identity.
4. Stop server last. Never `kill -9` between `save_state` tmp-write and
   `os.replace` (the window is small but the rule is absolute).

## 4. Start order (procedure — NOT executed)

1. Start server first; confirm `/health` + state loads with expected
   goals/tasks/workers keys.
2. POST `/tasks/reclaim_stale`: stale CLAIMED/RUNNING without result →
   quarantined with `recovery_reason=STALE_WORKER_EFFECT_AMBIGUOUS`,
   `reclaimed_tasks: 0` (`server/app.py:416-454`).
3. Start workers; each re-registers via heartbeat path. If a worker reports
   a `current_task` differing from the server's record, the server marks
   task+step `HUMAN_REQUIRED` /
   `recovery_reason=WORKER_RESTARTED_AND_LOST_STATE` and BLOCKs the goal
   (`server/app.py:185-215`) — this is the designed divergence signal,
   not a bug to work around.

## 5. Resume point (exact mechanics on BASE)

- Only resume action is `POST /tasks/<id>/resume {"action":"retry"}`
  (`server/app.py:resume_task`): allowed from HUMAN_REQUIRED,
  FAILED_VERIFICATION, FAILED_TERMINAL only.
- Retry sets task+step to QUEUED, `worker_id=None`, stamps `resumed_from`,
  sets goal ACTIVE. The next claim mints a **fresh attempt_id/dispatch_id**,
  so results of the superseded attempt can no longer bind.
- `force_success` returns 400 on BASE ("retry and verify instead") — there
  is no manual-success resume path. Do not invent one.

## 6. No-A-replay guard

- A-side (pre-restart attempt) never re-executes: stale A tasks land in
  quarantine (§4.2) or HUMAN_REQUIRED (§4.3); continuation happens only via
  fresh-attempt retry (§5).
- Mac side: a checkpoint whose `binding !=` current task binding is written
  aside as `checkpoint.quarantine-<uuid>.json` and never fed to the new
  task (`run_muse`, `daemon.py:340-346`). Foreign checkpoints cannot
  authorize resume (non-exec actions raise `MuseBindingError`).
- RUN_1 invalidation rules 5 (two SUCCESSes / silent re-execution) and 12
  (run without kill-restart segment is not RUN_2) apply unchanged —
  evidence: `courier_work/muse_zero_interference/MAC-06-01a0d7e1-20260926T144729Z/RUN_1_INVALIDATION.md`.

## 7. B continuation criteria

- B claims only a task in QUEUED status minted post-restart (fresh
  attempt/dispatch), never a pre-restart attempt id.
- B executes only after A-side outcome is durable (server task status +
  verifier verdict persisted via atomic save) — zero-relay: no human
  claim/resume/verify call between stages (invalidation rule 9).
- Full step protocol spec (ports, credentials, abort thresholds) already
  PASS-pinned in `courier_work/muse_mac_wall/results/
  MMAC-128_RUN1_RUN2_PHYSICAL_CANARY_CHECKLIST_AND_ABORT_SAFETY_SPEC.md`
  — reuse, do not rewrite.

## 8. Execution gate — WHY NOTHING WAS EXECUTED

- No RUN_1 physical PASS exists in durable results. The invalidation
  checklist records `BLOCKER=physical RUN_1 execution (Mac Antigravity)`.
- MMAC-128 PASS covers the *protocol spec*, not a physical run.
- Standing law: no RUN_2 before RUN_1 PASS; no RUN_1 before
  READY_FOR_PHYSICAL_RUN=YES.
- EXACT_RE_ARM_TRIGGER: durable RUN_1 PASS record (12-case matrix green on
  physical Mac Antigravity with prover-recomputed hashes) OR explicit
  operator authorization naming this checkpoint file.
- On trigger: execute §1 snapshot, then §3→§4→§5→§7 in order, recording
  hashes and timestamps at each step. Any deviation → abort to
  HUMAN_REQUIRED, never improvise a resume path.

DO_NOT_REPEAT_FINGERPRINT=MAC06-RUN2-RESTART-PREP-b1-4c1e24cc-noexec
