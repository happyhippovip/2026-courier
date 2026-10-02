# TEST-GAP + DEDUPE + STALE-ASSUMPTION REPORT (static, read-only)

## 1. TEST_MAP.yaml is 8 days / ~70 files stale (STALE, HIGH visibility)
- ops/ai/TEST_MAP.yaml (bound 0c8d1edd, 2026-09-18) names exactly 3 tests.
- tests/ actually contains ~75 test_*.py + conftest.py + test_execution_truth.mjs.
- T3 command references tests/test_execution_truth.mjs: FILE EXISTS (verified).
- T0 command references node/bash studio checks: not verified here (no shell).
- Suggested owner action: regenerate TEST_MAP from inventory (owner write; NOT
  done here — shared file, foreign writer scope).

## 2. Wall script -> test coverage matrix (OBSERVED)

| script | coverage | verdict |
|---|---|---|
| supervisor.py | test_supervisor, test_windows_muse_wall, test_muse_wall_gaps, test_muse_wall_jobs, test_muse_wall_staged_scaling | STRONG (unit, tmp isolated) |
| slot_state.py | same via imports | STRONG |
| muse_wall_launcher.ps1 | test_muse_wall_launcher_ps1 (parser + arg-array + workdir) | GOOD static |
| launch_safe_slot.ps1 | static x2 + functional x1 (see dedupe) | GOOD but DUPLICATED |
| launch_32_auto.ps1 | test_muse_32_auto_static only | STATIC ONLY — functional gap |
| probe_muse.ps1 | static only | STATIC ONLY — functional gap |
| install_desktop_shortcuts.ps1 | static only | STATIC ONLY — functional gap |
| stop_all_slots.ps1 | static only | STATIC ONLY — functional gap |
| launch_wall.ps1 | 1 shallow test (repo-root targeting) | FUNCTIONAL GAP (-Stage behavior) |
| start_all.ps1 | 1 shallow test | FUNCTIONAL GAP (-Slots/monitor) |
| status_wall.ps1 | 1 shallow test | FUNCTIONAL GAP (output contract) |
| stop_wall.ps1 | 1 shallow test | FUNCTIONAL GAP |
| watcher.py | 1 static assertion (canonical-first) | STRUCTURAL GAP (infinite loop, no seam) |

Functional gaps need a working shell runner (blocked this session); static pins
exist where the 2026-09-24/25 defects were (arg-array, workdir, safe-slot).

## 3. Dedupe findings
D-1 (REAL OVERLAP): tests/test_muse_safe_slot_static.py vs
  tests/test_launch_safe_slot_ps1.py — both pin the same script's structure
  (mandatory params, absolute dirs, no yolo/sandbox-disable, env capture order,
  finally-restore, scoped update/login, no ACL/creds, no IEX). The launch_ file
  additionally has 3 functional powershell tests. Unique to the static file:
  BypassSandbox token, --disable-approval present, single fixed invocation.
  Suggested owner action: merge those 3 assertions into test_launch_safe_slot_ps1
  and delete test_muse_safe_slot_static.py. (Report only; no deletion here.)
D-2 (NOT duplicates): test_queue_independence.py vs test_queue_independent.py —
  different tests (A-waits-B-executes vs daemon test), shared fixture style.
  Only a confusing name pair (LOW, cosmetic).
D-3 (NOT duplicates): test_supervisor.py / test_windows_muse_wall.py /
  test_muse_wall_gaps.py — complementary case splits with small intentional
  overlap (governor basics, reconcile). Keep all three.

## 4. Stale shared-memory assumptions (OBSERVED, for owner refresh)
S-1: MUSE_CONTINUOUS_WORK.yaml checkpoint iter9, heartbeat 2026-09-18, lane
  AWAIT_OWNER_PUSH_THEN_RECOMPUTE — 8 days old; unknown if owner pushed.
S-2: NEXT_WORK.yaml MEMORY-NEXT-01..08 all 2026-09-18 states; several say DONE/
  IMPLEMENTED but DLQ entries "kept open" — needs re-triage vs current HEAD.
S-3: WINDOWS_CONTINUOUS_WORK.yaml: W01-W08 COMPLETED by Antigravity, W09 PENDING
  (exact-SHA runtime proof prep — needs live process access; shell-less session
  cannot advance it; NOT taken).
S-4: OWNERSHIP_MAP.yaml bound to 0c8d1edd (2026-09-18); revalidation flag is
  true but no newer binding observed in working tree.
S-5: coordination/heartbeats/mac_heartbeat.json 2026-09-18, writer IDLE.
S-6: Memory notes "branch ledger-reconciliation-final, user pushed 2026-09-25"
  vs packed-refs divergence note — UNVERIFIABLE without git this session.

No shared files edited (all suggestions are owner-owned). No fake green:
gaps are gaps until a shell-capable session closes them.
