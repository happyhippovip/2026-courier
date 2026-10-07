# M208: Artifact Provenance Proof

## Goal
Prove that artifacts uploaded by workers are immutably bound to their specific execution dispatch, preventing spoofing, cross-task contamination, and replay attacks with mismatched data.

## Implementation & Proof
1. **Content-Addressed Storage**:
   - `scripts/artifact_store.py` stores artifact bytes in `blobs/<sha256[:2]>/<sha256>`, ensuring identical blobs are stored exactly once and cannot be mutated after write.
   
2. **Immutable Provenance Binding**:
   - `artifact_id_for(binding, name, sha256)` generates a deterministic, unguessable `artifact_id` by hashing a JSON payload containing the canonical `sha256` of the file, the artifact `name`, and the exact `BINDING_FIELDS`: `goal_id`, `task_id`, `attempt_id`, `dispatch_id`, and `worker_id`.
   - The resulting record is saved in `records/<artifact_id>.json` using an atomic write (`_atomic_write`).

3. **Verifier Trust Model**:
   - The verifier accesses `GET /artifacts/<id>` from the `ArtifactStore`.
   - `verify_uploaded_artifact` independently re-hashes the downloaded bytes, checking against the `record["sha256"]`.
   - It also cross-references all `BINDING_FIELDS` to ensure the artifact strictly belongs to the task being verified.
   - Because the worker only holds `dispatch_id` and the server enforces `dispatch_id` on the upload route, the worker cannot upload an artifact that impersonates another run or another task.
