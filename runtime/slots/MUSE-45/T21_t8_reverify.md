# T21 RESULT — T8 service-findings re-verification vs current tree (read-only)

MODE: shell-less LIGHT. P3 files READ ONLY (no edits). Sampled F-T8-1 + F-T8-2.

## 1. F-T8-1 double :8080 bind — STILL OPEN (RE-CONFIRMED, pins exact)
- server/app.py:1589-1590 (OBSERVED, line pins UNCHANGED since T8):
  `if __name__ == "__main__": app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8080)))`
- server/run_waitress.py:13 (OBSERVED): `serve(app.app, host='0.0.0.0', port=8080)`
- Motor-path flask + server-service waitress still bind the same default port
  with no guard/mutual-exclusion note in either file. No drift, no fix.

## 2. F-T8-2 AtLogon-not-boot — STILL OPEN (RE-CONFIRMED)
- scripts/install_motor_service.ps1:11, scripts/install_verifier_service.ps1:11,
  scripts/windows_worker/install_service.ps1:11: all still
  `New-ScheduledTaskTrigger -AtLogon`. No AtStartup/SYSTEM migration.
- server/install_server_service.ps1: still HKCU Run registration; line 44 still
  prints "start on boot" for what is a logon trigger — claim inaccuracy stands.
- RC proof steps 2-3 ("OS-owned, terminal-independent") still hold only while
  the Windows session stays logged on. Writer-scope decision, not made here.

## Pin-drift note (for T11 line-pin watchers)
T8's app.py:1589-1590 pin verified EXACT at current tree. This pin has not drifted.
