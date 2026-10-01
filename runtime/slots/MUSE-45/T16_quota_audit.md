# T16 RESULT — DLQ-05 quota-lock static audit at HEAD b927f106

MODE: shell-less LIGHT. Audited server/app.py lock paths + isolation test
+ CODEX packet + DLQ-05 entry. Production behavior re-verified at current
loose ref (prior audit was at 2026-09-18 heads). No execution.

## Verified mechanics (OK at current HEAD)
- Key derivation consistent at 3 sites: eligibility (259-262), claim resume
  + claim gate (755-757, 785-790), provider_wait (1425-1431).
- Replay monotonic: max(existing, new) (1431). Expiry resume: claim
  auto-resumes past lock (761). Double gate: eligibility False + claim
  PROVIDER_QUOTA_LOCKED while locked.
- Provider retries bounded (1419) -> FAILED_TERMINAL + goal BLOCKED (1436).
  wait_type allowlisted (1415), worker-mismatch 403 (1411), non-DISPATCHED
  409 (1409). Attempt identity preserved across waits (1424).

## Findings
P-T16-1 (MEDIUM-LOW) POOL SHARING STILL UNREALIZED — RE-VERIFIED TODAY.
worker_quota_pools is written NOWHERE in production (4 reads, all
.get(worker_id, worker_id) fallback; only the isolation test seeds it).
Effective deployed key = worker_id:provider, NOT pool:provider. Two workers
on one real credential do NOT share a lock. Packet Q1/Q4 (design vs
deployment-population, mapping authority) open since 2026-09-18; still
unanswered in every readable source. Harmless if 1 worker == 1 credential;
DLQ-05's original storm risk persists across workers otherwise. NOT new —
known-documented; contribution here = re-verified at b927f106, still true.
Owner: Google/quota design.

P-T16-2 (LOW) W08 STATUS AMBIGUOUS.
Lane footer says W08 COMPLETED, but the packet (its own evidence artifact)
says PHYSICAL_PENDING=W08 with Q3 open (restart persistence + expiry +
replay on a real server-owned pool config). Static half verified here;
physical half is unprovable without a populated pool + live server.
Same status-ambiguity family as D-T13-3. Owner: Windows-lane steward.

P-T16-3 (INFO) PACKET LINE PINS DRIFTED.
Packet cites app.py:710-750 + 1305-1325; code now at 720+/754-790 +
1391-1450. Re-pinning due (T11 family). Owner: packet steward.

## Disposition
Read-only mission: NO FIXES (server/quota = Google scope, P3-adjacent).
P-T16-1/2 handed to quota/Windows-lane owners.
No files outside runtime/slots/MUSE-45 touched.
