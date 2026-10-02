# HARVEST 01 — night round pass 1 (read-only)

BY=WIN-06 SESSION=01a0dcac-1002-7e02-bb95-adacfb630c52 DATE=2026-09-26
No source writes (own-slot checkpoint only). No tests, no canary, no subagents.
Peer work consumed, never redone. Stale context cleared at end.

## New peer results consumed
- WIN-03 W5_verify_peers: 14/14 CONFIRMED (incl. my RESULT_01 provider verdict
  V5-3, F1/F2 V5-4/5, census V5-1/2; + W02-01/W02-02/WIN-01-W2/MUSE-45-T18).
  N5-1 (WIN-01 stale "only slot" line), N5-2 (7-line drift watch). Valid
  AT READ TIME — subjects since partly deleted (see STALE).
- MUSE-45 T20: C-1/A-2/I-3 all STILL OPEN (re-confirmed). Timeline anchor:
  T20 read supervisor.py lines 222-225 this session -> wall *.py deleted AFTER.
- MUSE-45 T-D: G1 (DLQ-08 hang-abandon test gap, owner), G2 (provider-flag
  resolution via test pins) — G2's pin FILES now deleted (see STALE).
- WIN-01 CHECKPOINT: W1..W5 scope (process/ps1/leases/paths/preflight),
  pool-coverage claim, BLOCKED list (matches mine). W2 PS-W2-1 uninstall
  broad kill + safe-alt=stop_safe.py (safe-alt now DELETED).
- MUSE-45 checkpoint: T-B F1-F5 (stop.bat overbroad kill INDEPENDENT find,
  P3 regen collision, dual 8080 binders, 2 orphaned launchers, 3 venv
  strategies — cited, T-B packet has details).

## My spot-checks (independent, this pass)
- S-H1: T-D G2 pins GONE (test_muse_wall_staged_scaling.py + test_muse_wall_gaps.py
  both os-error-2) -> G2 resolution STALE; provider flag unpinned again.
- S-H2: soak_test.py GONE -> V5-9 SK-2 hazard MOOT on current tree (lesson
  persists for any re-added soak: no in-memory gate flips, no unconditional
  success, never run vs proof root).
- S-H3: W5 V5-4/5 subjects GONE (stop_safe.py + old daemon) -> W5 corroboration
  valid-at-read-time only; must not be cited as current.
- S-H4: demolition move-vs-delete: `admitted_count` appears ONLY in MUSE-45
  reports, zero implementation hits -> wall supervisor DELETED, not moved.

## Demolition inventory (direct-read os-error-2, this session)
Wall (8): supervisor.py, __init__.py, watcher.py, slot_state.py, soak_test.py,
launch_32_auto.ps1, muse_wall_launcher.ps1, config.json.
Worker (2): stop_safe.py, worker_status.py.
Tests (4): test_restart_resume_torture.py, test_muse_wall_staged_scaling.py,
test_muse_wall_gaps.py, test_windows_daemon_completeness.py.
Rewritten (not deleted): server/app.py (1400+ -> 562 lines), daemon.py
(403-line marker design -> 389-line phase machine, still evolving).
UNPROBED (no claim): start_all.ps1, probe_muse.ps1, install/uninstall ps1,
pyproject currency. Survivors verified post-churn: server/app.py v2,
daemon.py v2, stop.bat, start.bat, runtime/slots/* artifacts.
Pattern: coherent migration (wall removal + worker v2 + server slim) under the
active writer — NOT random tool failure (selective + peer-corroborated).

## Dedup map (ownership respected, zero double-work)
STOP: T-B + MW1-D6 + W2 + my X6 (convergent, cited). Leases/quarantine: WIN-01
W3 + MUSE-45 WATCHDOG/T14 + my MW2-R4 (cited). Coverage: MUSE-45 T10 (stale,
see NEXT_GAP). Error-contracts: WIN-03 W4 (motor/ledger) + my C1 (daemon-409,
resolved-moot). Verify-peers: WIN-03 W5. Installers: MUSE-45 T-B/T8, WIN-03/04
T7. Census: WIN-05. Restart fixtures: my MW3 (specs valid, mechanism refs stale).

## Contradictions / stale (consolidated)
- MW1-D1/D4 premises vs current daemon (X1/X2, prior note) — still open.
- W2 fix direction (use stop_safe) infeasible — safe-alt deleted (NEW).
- W5 V5-4..7 corroborations frozen at old rev (NEW). T-D 17/17 sweep stale
  (>=4 files gone) (NEW). T10 worker/wall tiers moot (subjects deleted) (NEW).
- Checkpoint 65/65 + queue.db-functional + provider-true claims: no tree
  support (standing). MUSE-45 WATCHDOG line refs stale, behavior holds.
- uninstall.ps1 current state UNPROBED (path unknown to me) — W2 finding
  carries forward unverified (not contradicted).

## CENTRAL_WRITER_INPUT (actionable only)
1. STOP path (top UNSAFE cluster, 3+ witnesses): stop.bat broad-kills
   (confirmed live); stop_safe deleted; uninstall broad per W2 with safe-alt
   gone. Re-establish exact-stop (PID+create_time ownership) and route both
   stop flows through it. Nothing else in this file outranks this.
2. FAILED-requeue idempotency rule (my MW2-R6): server v2 still re-queues any
   FAILED with fresh ids (app.py:388-390 + :329-331, current). Gate
   effect-critical retries on idempotency proof or human review.
3. Re-pin safety properties when code settles: provider flag unpinned (pins
   deleted with tests); governor/marker/queue daemon tests gone with old
   daemon; T10 map needs v2 redraw (see NEXT_GAP).
4. Evidence protocol during migration: revision-stamp all reports (file hash
   or Git SHA at read time); treat uncited line numbers as suspect;
   re-verify before citing. Evidence half-life is currently hours.
5. Stage-PASS lesson (A-2, survived its subject): any re-added wall tooling
   must machine-count live sessions; operator-checklist strings don't gate PASS.
6. v2 nits: daemon "200 IGNORED" docstring vs server ACK_DUPLICATE (cosmetic);
   worker observability gap after worker_status deletion (needs v2 equivalent?).

## NEXT_GAP (unowned, verified-absent)
V2 coverage + contract map: fresh T10-style map of the CURRENT tree (which
surviving tests cover rewritten daemon.py/server/app.py; integration_contract
currency vs v2 worker protocol incl. phase machine + 4xx/5xx split + msvcrt
locks). T10 describes deleted code; MW1 used the contract as anchor without
auditing it; nobody owns the redraw. Shell-less mappable (imports + paths);
behavioral pins need a runner. (Second: v2 worker observability spec.)
No peer owns it (frontier + checkpoint review); no wall/writer conflict
(read-only); no Mac scope.

## Stale context cleared
Pre-rewrite daemon/app/wall line refs (mine + cited peers') superseded by MW2
maint + this note. W5 N5-1 folded into WIN-05 census (dropped). Old claim_task
(720-812) observations dropped (file restructured). S2-supervisor code detail
still blocked (subject absent) — kept as one-liner, not re-derived.
Resume: re-probe demolition list + NEXT_GAP on next pass; IDLE if unchanged.
