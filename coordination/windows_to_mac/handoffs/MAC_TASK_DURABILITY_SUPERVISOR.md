# Autonomous Mac Handoff: MAC-TASK-DURABILITY-SUPERVISOR

**Handoff ID:** `HANDOFF-MAC-DURABILITY-01`  
**Dispatched By:** `WINDOWS_PC2_CHIEF`  
**Assigned To:** `MAC_CHIEF_01`  
**Created:** `2026-09-13T11:28:00Z`  
**Mission:** `SYMPHONY_POST_V1_AUTONOMY_CAMPAIGN`  
**Target:** macOS Persistent Supervision (`LaunchAgent` / KeepAlive Supervisor)

---

## 1. Objective

Implement and prove the smallest native persistent supervision solution appropriate to macOS for Mac Chief heartbeat and result monitor, upgrading Mac durability from `LIVE_SESSION_PROVEN` to `RESTART_PERSISTENCE_PROVEN`.

---

## 2. Identified Root Cause

In the current live session, the Mac heartbeat file (`coordination/heartbeats/mac_heartbeat.json`) is being actively written every 15 seconds (verified by SMB `mtime` transitions), but the JSON content contains a static `timestamp_utc: "2026-09-13T10:41:10.241771+00:00"`. This indicates the payload dictionary was instantiated outside the `while True:` pulse loop.

---

## 3. Required Deliverables & Verification

1. **Dynamic Payload Generation:**
   Inside the Mac heartbeat pulse loop, evaluate `datetime.now(timezone.utc).isoformat()` dynamically on every pulse.
2. **Persistent Supervisor (`launchd`):**
   Create a standard user LaunchAgent plist:
   `~/Library/LaunchAgents/com.symphony.mac_chief.plist` with:
   - `KeepAlive: true`
   - `RunAtLoad: true`
   - `StandardOutPath` and `StandardErrorPath` directed to `coordination/logs/`
3. **Verification Checklist:**
   - Heartbeat resumes automatically on process exit or reboot.
   - Result monitor resumes automatically and consumes `windows_to_mac/results/`.
   - Single writer instance enforced.
   - Zero duplicate ACKs and zero duplicate physical effects.
   - State reloaded from durable files upon boot.

---

## 4. Invariants

- **Windows V1 Frozen:** Zero changes to Windows Courier repository (`WINDOWS_V1_MUTATIONS = 0`).
- **Zero Spend:** `AUTONOMOUS_SPEND_EUR = 0.00`.
- **Coordination Transport:** All exchange through `\\192.168.178.162\coordination`.
