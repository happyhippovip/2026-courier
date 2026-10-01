# M218: Post-Publish SHA Binding

## Goal
Prove that Courier enforces payload integrity when publishing the final result back to the Codex coordinator (the `github_courier` integration).

## Implementation & Proof
1. **Schema Validation**:
   - `scripts/publish_courier_result.py` converts a local Courier `TASK` success into the global Codex `RESULT` format.
2. **Hash Re-verification at the Border**:
   - Before publishing, it recalculates the payload hash using standard JSON canonicalization:
     ```python
     def payload_hash(payload: object) -> str:
         return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
     ```
   - It strictly asserts `if result["payload_hash"] != payload_hash(result["payload"]): fail("payload hash mismatch")`
3. **Protection**:
   - This ensures that transit over any intermediate channel (like an operator copying files or automated relay scripts) has not tampered with the payload data intended for Codex.

## Conclusion
Courier safely extends trust back to the global coordinator by enforcing an independently calculated SHA binding immediately before formal publication.
