# MAC-FINISH-05 — Artifact Hash Capture Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-05
- **Area**: ARTIFACT_HASH_CAPTURE_PACKET
- **Status**: COMPLETE

Establishes the cryptographic artifact hash capture, comparison, and anti-tamper specifications.

---

## 2. Cryptographic Standard
- **Algorithm**: SHA-256 (`hashlib.sha256`)
- **Format**: 64-character lowercase hexadecimal string
- **Encoding**: UTF-8 bytes for text; raw binary stream for binaries.

---

## 3. Pre-Declared vs Verified Hash Protocol
1. **Pre-Declaration**: The task contract authoritatively specifies `expected_artifacts[path] = expected_sha256`.
2. **Worker Upload**: Worker generates artifact and uploads to `POST /artifacts/{task_id}`.
3. **Independent Verifier Fetch**: Verifier downloads artifact bytes via `GET /artifacts/{id}` directly from coordinator store.
4. **Independent Hash Calculation**:
   ```python
   actual_sha256 = hashlib.sha256(downloaded_bytes).hexdigest()
   ```
5. **Verdict Rule**:
   - `actual_sha256 == expected_sha256` -> `VERDICT: PASS`
   - `actual_sha256 != expected_sha256` -> `VERDICT: FAIL (TAMPER_DETECTED)`
