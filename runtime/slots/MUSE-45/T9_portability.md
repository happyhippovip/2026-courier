# T9 RESULT — Portability audit MAC vs WINDOWS (static, read-only)

MODE: shell-less LIGHT. All claims OBSERVED-in-file unless marked.

## Scope
Live code under scripts/ + server/*.py checked for hardcoded host/user/checkout
identity, Windows-only and Mac-only assumptions. Runtime caches, archived logs,
docs, and *.txt/*.log artifacts excluded (not shipped code).

## Findings

F-T9-1 (MEDIUM) HARDCODED WINDOWS-TARGET IDENTITY IN STUDIO TOOLING.
scripts/studio_local_tools.py:48,58,62-63 hardcodes the full Windows side of the
pairing: health URL http://192.168.178.87:8080/health, ssh alias 'windows-ai',
user 'lol', repo path C:\Users\lol\2026-workspace\2026-courier.
Any other IP/user/checkout breaks remote SHA sampling (fails silent -> display
evidence only, no state corruption; lines 71-73). Owner: studio scope
(MUSE-adjacent). Fix direction (NOT applied, read-only): config/env for
host+alias+user+repo path.

F-T9-2 (LOW) HARDCODED MAC USERNAME IN AGY FALLBACK PATH.
scripts/mac_worker/daemon.py:240 appends ":/Users/user/.local/bin:..." to PATH
when resolving `agy`. Correct only for user `user`; any other Mac account
loses the ~/.local/bin fallback. Fix direction: os.path.expanduser.
Owner: mac worker scope.

F-T9-3 (LOW) POSIX-ONLY /tmp IN TEST-ONLY SERVER PATH.
server/app.py:24 (P3, read-only here) uses /tmp/mock_replenish.txt inside the
REPLENISHMENT_TEST branch. Stock Windows has no /tmp -> this branch raises
FileNotFoundError on Windows instead of returning unique instructions.
Test-only path, but it makes that test scenario Windows-unrunnable.
Owner: P3/server scope. Fix direction: tempfile.gettempdir().

F-T9-4 (INFO) ROOT SCRATCH SCRIPTS ARE WINDOWS-USER-PINNED.
get_w*.py / get_issue37.py / find_*.py (repo root, 10+ files) hardcode
C:\Users\lol\.gemini\...\transcript_full.jsonl; proof_w25.py uses wmic +
shell=True (Windows-only). Treated as scratch, not product code.
Tracked-state UNKNOWN (no shell -> no git check). Suggestion for owner:
move to archive/ or gitignore. No action taken here.

## Verified portable (OK)
- File locking: scripts/agent_handoff_ledger.py:624-645 (msvcrt vs fcntl). OK.
- Process mgmt: scripts/agent_session_manager.py:26,61 (win32->psutil,
  posix->ps/signals). OK.
- Worker wrappers: mac_worker/daemon.py:245,332 (skip .sh wrapper on nt,
  hasattr-guarded killpg). OK.
- Interpreter: sys.executable used across 15+ call sites; zero "python"
  string literals in subprocess calls under scripts/+server/. OK.
- No .ps1/.bat references from scripts/ or server/ python. OK.
- /Users/user appears ONLY in archive/night_scratch logs (Mac tracebacks).
  No live-code reference. OK.
- C:\Users\lol appears ONLY in docs/scratch/logs + F-T9-1. OK otherwise.

## Disposition
Read-only mission: NO FIXES APPLIED. F-T9-1 -> studio owner, F-T9-2 -> mac
worker owner, F-T9-3 -> P3/server owner, F-T9-4 -> repo hygiene owner.
No files outside runtime/slots/MUSE-45 touched.
