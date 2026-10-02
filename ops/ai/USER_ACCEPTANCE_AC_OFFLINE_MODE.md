# User Acceptance: Offline Mode Handling

**User Problem:** What does Courier do if my internet connection drops while it is waiting for a provider?
**Current Runtime Truth:** Unclear if the watchdog correctly differentiates between a stalled provider (timeout) and a local network failure (offline).
**Acceptance Requirement:** Courier should detect local offline status immediately (e.g., DNS failure) and enter an `OFFLINE_BACKOFF` state, notifying the user "Waiting for Network..." instead of repeatedly failing tasks.
**Missing System Support:** Network connectivity pre-check in `run_chief_commander.py` before claiming tasks.
**Preparable Now:** Yes, the UX expectation can be mapped.
**Blocked Until:** Core Freeze and Product Shell opening.
