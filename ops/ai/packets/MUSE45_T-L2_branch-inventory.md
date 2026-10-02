# MUSE-45 T-L2 — fix-cb1-new branch inventory (read-only)

Branch fix-cb1-new @ 329abd80 (post-switch tree). Shell DOWN; static only.
Nothing modified but this packet.

## Branch character (OBSERVED)

- Carries the MAC Muse-supervisor lineage: scripts/mac_worker/muse_supervisor.py
  (canonical worker path: per-slot daemon.py, register->claim->result,
  RESULT_READY re-sent, STARTED released-never-replayed, PAUSED_ERROR after
  CRASH_LIMIT, 1-4-8-16-32 ramp gated on resource metrics, exact-own-daemons
  stop). Matches the START_HERE description of supervisor/canonical-muse-runtime.
- mac_worker/ set here (14 files): adds muse_adapter.py, muse_prompt.md,
  muse_supervisor.py, runtime_state.py vs the ledger-line set.
- tests/test_muse_convergence.py: "Focused canonical runtime regressions. No
  real Muse/provider/Keychain calls." WORKSPACE constant = the MAC repo path
  (/Users/user/Downloads/2026-courier) — Mac-pinned test constant (T9-family).
- "cb1" meaning: UNKNOWN (4 repo-wide hits: 2 events JSONs + my 2 packets;
  no branch manifest in tree). Not chased further.

## Absent vs pre-switch tree (tracked, verified gone)

- scripts/agent_handoff_ledger.py, scripts/courier_continue.py,
  scripts/windows_muse_wall/* (whole dir), ops/ai/* (tracked),
  AGENTS.md + .agents/* (whole dir), docs/RELEASE_CANDIDATE.md,
  ledger/motor/wall test files, server service-installer path.
- server/app.py: older/smaller shape (claim :263, flask main :561-562).
- windows_worker/: no run_loop.bat/stop_safe.py/worker_status.py/start.py.

## Portability notes (static)

- muse_supervisor.py imports fcntl at top (POSIX-only) -> cannot run on
  Windows. This Windows checkout now carries a Mac-only wall supervisor.
  Whether the pivot is for review or execution is UNKNOWN; no run attempted
  (shell DOWN + foreign scope either way).
- My governing AGENTS.md + .agents/rules are absent from this tree. I continue
  under the mission prompt + already-read autonomy content + memory + live-show
  rules. No rule content re-derived from absence.

## Verdict

fix-cb1-new = Muse-supervisor (Mac) lineage + older server + reduced worker
tooling. All pre-switch ledger/motor/wall evidence stays branch-scoped to the
old tree (see INCIDENT + T-L1 packets). No edits, no checkout, no contact.
