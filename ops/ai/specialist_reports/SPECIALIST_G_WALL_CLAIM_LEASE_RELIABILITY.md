# Specialist Report G — Wall Claim / Lease Reliability

**Role**: `WALL_CLAIM_LEASE_REVIEWER`  
**Host**: MAC  
**Status**: AUDITED / VERIFIED  

---

```text
CLAIM_RULES_PROVEN=
[x] ONE_LIVE_CLAIM_PER_TASK: Enforced by atomic filesystem file creation and server state mutex. Verified in ops/ai/wall_claims/ and server/app.py.
[x] CLAIM_IDENTITY_BINDING: Claim payload durably records {"slot", "host", "provider", "status", "claimed_at"}.
[x] NO_CLAIM_STEALING: Workers inspect existing claims before write; if claimed by live worker, claim is skipped.
[x] LEASE_EXPIRY_RECOVERY: 300-second lease window (time.time() + 300). Tasks whose lease expires can be reclaimed or moved to HUMAN_REQUIRED.
[x] SESSION_RESTART_CONTINUITY: Claims and state persist in filesystem JSON (central_state.json and wall_claims/*.claim.json). Model context resets or /clear do not drop durable claims.
[x] NO_DUPLICATE_EXECUTION: A claimed or running task cannot be claimed by a second worker; claim_task() returns WORKER_BUSY or assigns next eligible task.

GAPS=
- Coordinator does not run a dedicated background timer thread to automatically sweep expired leases; lease expiry is evaluated passively on incoming claim_task calls. (Non-blocking for pilot single-node operation).

CONTRADICTIONS=
- None. Claim mechanics between wall files and central coordinator are consistent.

SMALLEST_REQUIRED_FOLLOWUP=
- Maintain passive lease expiry verification for pilot; defer proactive timer thread to post-pilot milestone.
```
