# T24 RESULT — T9 live-code portability re-verification (read-only)

MODE: shell-less LIGHT. All three T9 live-code pins re-read at current tree.

## 1. F-T9-1 studio hardcoded Windows identity — STILL OPEN (pins EXACT)
- scripts/studio_local_tools.py:48: `http://192.168.178.87:8080/health`
- scripts/studio_local_tools.py:58: `Set-Location C:\Users\lol\2026-workspace\2026-courier`
- scripts/studio_local_tools.py:62-63: `ssh ... windows-ai powershell ...`
- T9's cited pins (48,58,62-63) all exact, zero drift. Fail-silent display-only
  behavior (lines 70-73) also unchanged. Studio-owner scope; no touch here.

## 2. F-T9-2 agy Mac-username fallback — STILL OPEN (pin EXACT)
- scripts/mac_worker/daemon.py:240:
  `shutil.which("agy", path=... + ":/Users/user/.local/bin:...")`
- Still breaks the ~/.local/bin fallback on any non-`user` Mac account.
  Mac-worker-owner scope; no touch here.

## 3. F-T9-3 P3 REPLENISHMENT_TEST /tmp branch — STILL OPEN (pin EXACT)
- server/app.py:24 (P3 READ, no edit): `counter_file = "/tmp/mock_replenish.txt"`
- Windows FileNotFoundError behavior for that test branch stands. P3 scope.

## Report-hygiene note (T9 internal, minor)
T9 line 22 documents the live /Users/user reference (F-T9-2) while line 50
says "No live-code reference". Read line 50 as "no OTHER live-code reference
outside F-T9-2" (T9 scope was scripts/+server/; tests/ was out of scope and
is covered separately by T23). Suggested one-word amend for a future T9 edit;
not applied (predecessor report, keep intact).
