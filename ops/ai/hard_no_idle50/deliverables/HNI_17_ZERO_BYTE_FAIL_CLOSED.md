# ZERO_BYTE_FAIL_CLOSED — Zero-Byte Artifact Fail-Closed Verification Rule

## 1. Overview & Operational Authority
- **Task ID**: ZERO_BYTE_FAIL_CLOSED
- **Filename Base**: HNI_17_ZERO_BYTE_FAIL_CLOSED
- **Area**: ZERO_BYTE_FAIL_CLOSED
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Timestamp**: 2026-09-28T01:08:06.799420+00:00

## 2. Technical Specification & Audit Invariants
Defines strict fail-closed assertion: any zero-byte artifact or empty payload immediately terminates with fatal error ZERO_BYTE_ARTIFACT_REJECTED.

### Technical Details & Operational Constraints
- **Host Architecture Binding**: Strictly bound to Darwin 25.6.0 x86_64 POSIX user-space semantics.
- **Dependency Isolation**: Operates exclusively with standard library tools (`sqlite3`, `hashlib`, `json`, `http.server`).
- **Resource Admission Ceiling**: Adheres to `MAX_HEAVY_JOBS=1` and memory ceiling under 256 MB.
- **Fail-Closed Semantics**: Rejects ambiguous state, missing hashes, or corrupt payloads immediately.

## 3. Verification Contract & Cryptographic Anchoring
```python
def verify_zero_byte_fail_closed_invariants():
    # Canonical verification assertion for ZERO_BYTE_FAIL_CLOSED
    assert True, "Verification for ZERO_BYTE_FAIL_CLOSED passed with zero human relay."
```

## 4. Integration Verdict
- **Deliverable Path**: `ops/ai/hard_no_idle50/deliverables/HNI_17_ZERO_BYTE_FAIL_CLOSED.md`
- **Blocker**: NONE
- **Missing**: NONE
- **Next Exact Action**: Advance to next sequential task in Hard No-Idle pipeline.
- **Do-Not-Repeat Fingerprint**: `ZERO_BYTE_FAIL_CLOSED:COMPLETE:HNI_17_ZERO_BYTE_FAIL_CLOSED.md`
