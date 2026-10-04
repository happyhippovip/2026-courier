# MUSE-45 T-F — Freshness re-scan + stop-path contrast + portability (read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static tree evidence only (shell DOWN). Nothing modified but this packet.

## Freshness: NO foreign changes since T-A baseline

- job.json: still exactly 16 (MUSE-01..16). DONE states: still exactly 16.
- config.json: still active_limit=16, provider_launch_enabled=false.
- ops/ai/packets/: 18 files = 13 foreign baseline + my 5 (T-A..T-E).
  No foreign packet additions, no slot/job/config movement during my session.

## Stop-path contrast (extends T-B F3)

- `scripts/windows_worker/stop.bat`: overbroad CIM command-line kill (F3, stands).
- `scripts/windows_muse_wall/stop_all_slots.ps1`: CLEAN — routes every slot
  through `supervisor stop --slot` (exact PID+create_time identity), plus explicit
  no-broad-kill header. Zero Stop-Process/Terminate/taskkill/pkill/killall
  strings in the whole windows_muse_wall/*.ps1 set.
- Verdict: the exact-identity pattern already exists in-repo (wall); the worker
  stop path is the lone outlier. Owner fix direction is in-tree precedent, not
  new design. Not fixed by me (Google scope, needs shell).

## Portability notes (static)

- Worker daemon layer is dual-platform: scripts/mac_worker/*.sh suite
  (install/start/stop/status/uninstall/setup_keychain/limit_wrapper) + plist +
  daemon.py + health_check.py mirrors scripts/windows_worker/*.bat + daemon.py.
- Muse WALL orchestration (wt.exe wall, probe_muse.ps1, launch_32_auto.ps1,
  install_desktop_shortcuts.ps1) is Windows-only: no .sh twins, wt.exe and
  Scheduled-Task cmdlets have no Mac equivalent in tree.
- Consistent with RELEASE_CANDIDATE OS_SUPPORT (Windows primary; Mac/Linux
  "supported, not run" = runtime/worker scope, not wall). No contradiction found.
  Wall-on-Mac would need new Terminal/tmux orchestration (absent; owner roadmap).
