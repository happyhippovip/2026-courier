# User Acceptance Requirement 02: Artifact Receipt & Provenance (User-Visible Proof)

## 1. User-Visible Ambiguity
When Courier completes a task that produces an artifact (e.g., a report, export, build binary, or proof file), the user sees:
`"artifacts": [{"artifact_id": "art-7f9a8b...", "path": "report.pdf"}]`.
The user has no simple way to know:
- Where is this file stored on disk?
- How big is it, and is it complete?
- Was it genuinely verified, or did a worker produce empty / mock bytes?
- How can the user visually check the cryptographic fingerprint without manual Python or terminal commands?

## 2. What the System Can Actually Prove Today
The authoritative server state (`ArtifactStore` & `server/app.py`) tracks:
1. `record = ARTIFACT_STORE.get_metadata(artifact_id)` with:
   - `name`: Original artifact filename.
   - `size`: Exact byte length.
   - `sha256`: SHA256 computed by the server from raw incoming stream.
   - `task_id`, `goal_id`, `worker_id`.
2. Verifier confirmation:
   - `task["verification"]["verdict"] == "PASS"` confirms that `record["sha256"]` matches the task's immutable `expected_sha256`.
3. Disk location:
   - Storage directory: `ARTIFACT_STORE.storage_dir / record["storage_key"]`.

## 3. Concrete Acceptance Requirement
Every completed task producing artifacts must provide a human-readable **`Artifact Receipt`**:
1. **`name`**: Human filename (e.g. `report.pdf`).
2. **`size_formatted`**: Readable size string (e.g. `42.5 KB`).
3. **`sha256_fingerprint`**: Shortened format `abcd1234...ef567890` for rapid visual verification against task inputs.
4. **`integrity_status`**:
   - `VERIFIED_MATCH`: Server bytes match task expected SHA256.
   - `EXTERNAL_PRODUCED`: Externally produced artifact (e.g., GitHub CI run).
   - `HASH_MISMATCH`: Tampering detected.
5. **`file_access`**:
   - Local filesystem path (if on the same machine).
   - Direct download URL `/artifacts/<artifact_id>`.

## 4. Required Runtime State & Evidence
- **State Fields**:
  - `task["result"]["artifacts"]`
  - `task["verification"]`
  - `ARTIFACT_STORE.meta[artifact_id]`
- **Evidence Verification**:
  - Automated test verifying that when an artifact is uploaded and verified, the receipt contains matching SHA256, human-readable file size, and clean integrity status.
