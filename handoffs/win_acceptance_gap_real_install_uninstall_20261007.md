# WIN Acceptance GAP 3 — real install -> first launch -> real uninstall (Rule 0 steps 1-2, 12)

Date: 2026-10-07. Worker: Windows clean-machine acceptance (shell-less session).
HEAD verified: `integration/v1` = `b9fc486a` (2026-10-07T17:41:13Z).
All file facts below observed via raw read at that HEAD, not inferred.

## Chain legs

install -> first launch -> worker start -> uninstall -> user-data behavior.

## Finding (observed)

The REAL installer scripts are executed by NO test and NO CI job:

1. `scripts/windows_worker/install.ps1` (3218 bytes):
   - Machine-wide `%ProgramFiles%\CourierWorker` + SYSTEM scheduled task
     at startup, Highest. V1 baseline (`docs/V1_RULE_0.md`) prescribes a
     per-user installer; `launcher/` contains only `CourierLauncher.cs` +
     `build_launcher.ps1` (no Inno Setup; PR #133 explicitly adds none).
   - Blocking `Read-Host` for server URL, API key, worker id: no
     non-interactive flags, so clean-machine CI/human-free runs cannot
     use it.
   - Default server `http://192.168.178.162:8080` (LAN IP), undocumented.
   - Token written via plain `Set-Content`, no file ACL (any local user
     can read `%LOCALAPPDATA%\Courier\run\controller.token`).
   - Copies `$PSScriptRoot\*` into Program Files (self-copy incl. zip,
     exes, scripts); no version check, no rollback.
2. `scripts/windows_worker/uninstall.ps1` (1510 bytes):
   - Admin-only (`exit 1` otherwise): per-user uninstall impossible.
   - Hardcoded `C:\Users` profile iteration (breaks on relocated profiles).
   - Preserves `courier.db` + logs, deletes `config.json` + `run/`
     (intended per Step 19) — but offers NO `-RemoveUserData` opt-in,
     although Rule 0 step 12 allows removal on explicit user choice.
     The choice does not exist.
3. The harness builds `Courier.exe` directly and ends with
   `shutil.rmtree(courier_dir)`; PR #157 keeps the scripts unexecuted
   ("A live run on a clean machine remains unproven") and checks the
   uninstall contract by parsing script text only.

## Why this scope is free

Same ownership check as GAP 1/2 (open PRs exactly #132-#159 at check
time): no PR executes or modifies install.ps1 / uninstall.ps1 live.
#133 owns packaging build+smoke of the exe, not these scripts.
Re-verify before writing code: ownership shifts fast in this area.

## Live-evidence status

BLOCKED in this session: shell sandbox setup fails, no local execution.
NOT claimed as proven. Additionally a live uninstall run needs a
scratch VM (machine-wide ProgramFiles + SYSTEM task + all-profiles
`C:\Users` writes are destructive on a dev box).

## Runbook (scratch Windows VM, repo at integration/v1)

1. Snapshot VM. Run `install.ps1` with piped stdin answering prompts
   (or pre-seed `%LOCALAPPDATA%\Courier\config.json` + token);
   record: exit code, files in Program Files, task registered/running,
   token file ACL (`icacls`), first-launch token + hub status.
2. Execute one synthetic task via controller API; record COMPLETE.
3. Close via console-window close; record: processes gone in <=15s?
   (`Get-Process Courier*`, python children of the job).
4. Run `uninstall.ps1` (admin); record: task gone? Program Files gone?
   `courier.db` + logs preserved? `config.json` + `run/` gone?
   interactive processes (if any) handled?
5. Revert VM to snapshot.

## Pass criteria (for the owning lane, suggested L6)

- FAIL today (predicted): non-interactive install impossible (Read-Host);
  token ACL open; no user-data-removal choice; live path wholly unproven.
- Fixed state: documented unattended install (flags or answer file),
  hardened token ACL, explicit user-data choice on uninstall, and one
  recorded live VM run covering steps 1-12 of the Rule 0 acceptance list.
