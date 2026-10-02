# M217: Result Provenance

## Goal
Prove that the outcome of a task (the `DurableResult`) is uniquely bound to the specific execution run, protecting the integrity of the system against result swapping or tampering.

## Implementation & Proof
1. **Canonical Identity Creation**:
   - `scripts/integration_contract.py` (`verify_result` / `validate_durable_result`) constructs an `identity` dictionary encompassing the strictly immutable fields: `goal_id`, `task_id`, `attempt_id`, `dispatch_id`, `worker_id`, `run_id`, `status`, and `artifacts`.
2. **Cryptographic Binding**:
   - It hashes this structured identity into a unique `result_id`:
     ```python
     payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
     identity["result_id"] = f"result-{hashlib.sha256(payload).hexdigest()}"
     ```
3. **Immutability Enforcement**:
   - If any field (like status, artifacts, or attempt) is tampered with by an active network adversary or a malfunctioning worker, the payload hash will diverge. 
   - The verifier (`scripts/courier_verifier.py`) re-verifies these properties on the backend, checking that the independent hash of uploaded artifacts matches the expected outcome.

## Conclusion
Courier establishes strong cryptographically bound Result Provenance by sealing the precise execution context (`attempt_id`, `dispatch_id`, `run_id`) into a deterministic `result_id` hash.
