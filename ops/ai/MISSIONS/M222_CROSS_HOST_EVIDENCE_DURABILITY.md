# M222: Cross-Host Evidence Durability

## Goal
Prove that physical evidence (artifacts) produced on one isolated host is durably exchanged and verified on a strictly different host (the independent verifier).

## Implementation & Proof
1. **Producer Isolation (Windows/Mac)**:
   - A physical runner (e.g., `daemon.py` on Windows) generates evidence files natively.
   - It executes `upload_pending_artifacts`, streaming the byte payload to the Courier Server (`POST /artifacts`).
2. **Consumer Isolation (Verifier)**:
   - The verifier (`scripts/courier_verifier.py`) operates in a distinct security context. It does *not* read from the worker's disk, nor does it share a file system.
   - It performs an explicit `GET /artifacts/<id>` from the centralized Courier ArtifactStore, verifying the `SHA-256` hash of the downloaded stream against the payload.
3. **Immutability Check**:
   - Artifact content is addressable by its payload hash, ensuring that the physical bytes produced by the worker exactly match the bytes reconciled by the cross-host verifier.

## Conclusion
Courier seamlessly orchestrates zero-trust evidence validation across heterogeneous hosts (e.g., Windows execution verified by a Linux/Mac control plane).
