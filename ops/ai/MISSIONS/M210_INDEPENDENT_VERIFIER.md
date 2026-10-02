# M210: Independent Verifier Authority

## Goal
Prove that the Courier architecture inherently prevents a compromised or faulty worker from unilaterally asserting its own success by cryptographically isolating the verification role from the execution role.

## Implementation & Proof
1. **Separation of Keys**:
   - `server/app.py` defines two distinct authorization realms: `COURIER_API_KEY` for workers (`@require_auth`) and `COURIER_VERIFIER_API_KEY` for the verifier (`@require_verifier_auth`).
   - The server enforces that these two keys must not match (`if VERIFIER_API_KEY == API_KEY: ... 503`). This guarantees that a leaked worker token cannot be used to invoke `/tasks/verify`.

2. **Separation of Identity**:
   - The `/tasks/verify` endpoint strictly enforces `if verifier_id == task.get("worker_id"): return 400`. A worker process cannot masquerade as the verifier even if it magically obtained the verifier key.

3. **Separation of Evidence Validation**:
   - The verifier (`scripts/courier_verifier.py`) does not run on the worker. It fetches the canonical artifact blob from the server via `GET /artifacts/<id>` and independently hashes the payload. It does not trust the `sha256` value claimed by the worker in the `DurableResult` without independently arriving at the exact same hash from the server's byte storage.

## Conclusion
Because verification requires a distinct authorization key, a distinct identity, and an independent cryptographic hash computation of server-owned bytes, no worker can self-certify a successful result.
