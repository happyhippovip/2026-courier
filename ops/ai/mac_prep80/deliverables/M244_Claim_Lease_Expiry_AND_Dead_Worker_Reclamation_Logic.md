# M244 — Claim Lease Expiry & Dead Worker Reclamation Logic

## 1. Overview & Authority
- **Task ID**: M244
- **Area**: LEASE_RECLAMATION
- **Status**: COMPLETE

## 2. Reclamation Logic
- Leases expire after 30 minutes without heartbeat.
- Harvester resets abandoned claims to `READY` for other workers.
