# MW4 Featherlight Process Audit — Windows (READ_ONLY, no kills)

Date: 2026-09-26. Host: Windows. 454 processes total. No stress tests, no kills, no arch changes.

## Ranked findings (evidence-backed, Courier-relevant first)

### 1. 29 idle muse-bin TUIs hold 3.9 GiB RAM
Evidence: `Get-Process muse-bin*` = 29 procs, WS sum 4167585792 bytes (~3.88 GiB), cumulative CPU ~25k s.
Includes wall slots MUSE-03..MUSE-16 (live since 25.09 21:0x) plus interactive sessions. Largest idle cost.

### 2. Duplicate dead supervisor shells, script missing
PIDs 18324 + 9008 (parent: Courier Control terminal 16284), identical cmdline:
`powershell.exe -NoExit -Command "cd C:\Users\lol\2026-workspace\2026-courier; python scripts\courier_supervisor.py"`
Evidence: `Test-Path scripts/courier_supervisor.py` = False; both shells have ZERO children; idle since 25.09 20:54.
Duplicate supervisor invocation that never produced a supervisor.

### 3. Orphaned launcher trees, sources deleted underneath
- PID 8132: bare `powershell.exe` (parent 7628 dead = orphan), 14 children = slot launchers for MUSE-04..16.
- The launcher source `scripts/windows_muse_wall/launch_safe_slot.ps1` referenced in those cmdlines: `Test-Path` = False.
- PID 11988: second bare orphan powershell, owns MUSE-03 chain (6044>4652>13732) — wall split across two orphaned parents.
- PID 6064 (wall launcher, parent 12056 dead) and 16284 (Courier Control WT, parent 17648 dead) also orphaned.
Effect: 14-slot wall cannot be relaunched/repaired from its original paths.

### 4. Wall display polls every 2s against the WRONG root
`.codex/worktrees/windows-muse-wall/.../wall_display.py:34-39`: `while True: cls, print(render()), sleep(2)`.
Runs as 3-proc chain 6064 (ps) > 8544 (.venv py) > 12200 (uv py) since 25.09 15:46.
Evidence of root mismatch: wall `--root` = worktree `.../scripts/windows_muse_wall`; worktree `MUSE-04/state.json` = READY/process null/workdir under `.codex/...`, while live MUSE-04 muse-bin uses workspace `2026-workspace/2026-courier/runtime/slots/MUSE-04/workdir`. Display loop (~43k iterations/day x N slot reads) supervises nothing live.

### 5. Three wrapper shells per idle slot (~42 procs)
Per wall slot: `launch_safe_slot.ps1` ps > `cmd /c muse.cmd` > `.muse-launcher.ps1` ps > muse-bin.
Evidence: MUSE-04..MUSE-16 each show 4 chained processes in Win32_Process; shell census 61 powershell / 35 cmd / 45 conhost / 14 OpenConsole. Idle wrapper overhead per slot ~3x.

### 6. Cross-tree invocation + stripped source dir
- Wall python: `.venv` interpreter from `2026-workspace/2026-courier` executes script from `.codex/worktrees/...` (mixed ownership).
- `2026-workspace/2026-courier/scripts/windows_muse_wall/` contains only `runtime/` + `__pycache__/` (no .py, no .ps1), yet live cmdlines point into it; stale `supervisor.cpython-314.pyc` written 26.09 12:xx with no matching source.

### 7. process_matches trusts PID + create_time only (low)
`slot_state.py`: match = `abs(create_time delta) < 1.0`; recorded `owner_token`/exe/cmdline not verified. PID-reuse misattribution window. Code-level, no live incident observed.

### 8. Log growth: NO issue (negative finding)
- `supervisor.py:60-63` rotates supervisor.jsonl at 128 KiB. Courier runtime logs ~20 KiB each; worktree runtime total 538 KiB/145 files; `muse_error.log` 0 bytes.
- Watch-only: Muse session store 1296 files / 72 MB (Muse-owned, not Courier).

Out of scope (not Courier): `agy` 53k CPU-s, ChatGPT renderers, 3x claude.exe, browsers.

## Method
Read-only: Win32_Process cmdlines/parents, Get-Process CPU/WS, Test-Path, Select-String + bounded reads of wall_display.py / supervisor.py / slot_state.py. Nothing started, stopped, or modified except this report.
