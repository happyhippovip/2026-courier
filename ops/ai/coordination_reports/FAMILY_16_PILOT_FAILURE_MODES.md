# Family 16: Pilot Failure Modes & Bounded Handling Matrix

**Status**: SPECIFIED  
**Principle**: Fail Closed, Preserve State, Zero Silent Corruption

---

## 1. Concrete Failure Modes Matrix

| Failure Mode | Trigger Event | Immediate System Action | User View / Remediation |
|---|---|---|---|
| **Provider Unavailable** | LLM API returns 500 / 503 / 429 rate limit | Worker pauses with exponential backoff (up to 3 retries); does not fail goal. | Displays `ARBEITET (Warte auf API-Kapazität...)`. |
| **Worker Dies / Crashes** | Worker process terminates mid-execution | Task lease expires after 300s; coordinator moves task to `HUMAN_REQUIRED`. | Displays `BRAUCHT DICH: Worker unerwartet beendet`. User runs restart command. |
| **Laptop Sleeps** | User closes laptop lid during active workflow | Timers pause; upon wake-up, heartbeat resumes. If >300s, task transitions safely to quarantine. | Displays `ARBEITET` upon wake or requests resume if connection timed out. |
| **Internet Outage** | Network drop prevents artifact upload | Worker retains local artifact and retries upload; does NOT re-run generation command. | Retries silently; no double-execution. |
| **Credential Expires** | Provider API token returns 401 Unauthorized | Worker halts task, reports `AUTH_FAILURE`; coordinator marks task `BLOCKED`. | Displays `BRAUCHT DICH: Bitte API-Schlüssel aktualisieren`. |
| **Result Returns Twice** | Network packet duplicate delivery | Coordinator recognizes identical `(dispatch_id, result_id, status)` and responds `ACK_DUPLICATE`. | Transparent; zero effect on workflow progress. |
| **Result Arrives Stale** | Late result from superseded attempt | Coordinator rejects with HTTP 400 (`attempt_id mismatch`). | Ignored; active attempt continues. |
| **Artifact Missing** | Result payload submitted without referenced file | Verifier detects missing artifact in server store and returns `FAIL`. | Task fails verification; moves to retry or `HUMAN_REQUIRED`. |
| **Artifact Wrong/Corrupted**| Server store SHA-256 does not match expectation | Verifier computes mismatch and issues `FAIL`. Status becomes `FAILED_VERIFICATION`. | Workflow halts safely; no corrupted state propagated. |
| **Restart During Verify** | Coordinator killed while verifier is processing | Upon restart, task status remains `RESULT_RECEIVED`; verifier re-polls and completes verdict. | Recovers seamlessly without re-running worker execution. |
| **User Interrupts** | User presses Ctrl+C or sends cancel signal | Coordinator writes `CANCELLED` status to state JSON and releases worker lock. | Displays `FERTIG: Vom Nutzer abgebrochen`. |
| **Human Decision Needed** | Task encounters ambiguous conflict or file overwrite | Coordinator marks step `HUMAN_REQUIRED`, pauses goal. | Displays `BRAUCHT DICH: [Entscheidungsfrage]`. |
