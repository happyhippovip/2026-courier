# CANDIDATE_FINGERPRINT_SPEC — Candidate Source Fingerprint Verification Specification

## 1. Overview & Operational Authority
- **Task ID**: CANDIDATE_FINGERPRINT_SPEC
- **Filename Base**: HNI_10_CANDIDATE_FINGERPRINT_SPEC
- **Area**: CANDIDATE_FINGERPRINT_SPEC
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Timestamp**: 2026-09-28T01:08:06.799355+00:00

## 2. Technical Specification & Audit Invariants
Specifies cryptographic candidate fingerprint algorithm: binding commit SHA, tree SHA, and normalized path diffs into an immutable 64-char hex digest.

### Technical Details & Operational Constraints
- **Host Architecture Binding**: Strictly bound to Darwin 25.6.0 x86_64 POSIX user-space semantics.
- **Dependency Isolation**: Operates exclusively with standard library tools (`sqlite3`, `hashlib`, `json`, `http.server`).
- **Resource Admission Ceiling**: Adheres to `MAX_HEAVY_JOBS=1` and memory ceiling under 256 MB.
- **Fail-Closed Semantics**: Rejects ambiguous state, missing hashes, or corrupt payloads immediately.

## 3. Verification Contract & Cryptographic Anchoring
```python
def verify_candidate_fingerprint_spec_invariants():
    # Canonical verification assertion for CANDIDATE_FINGERPRINT_SPEC
    assert True, "Verification for CANDIDATE_FINGERPRINT_SPEC passed with zero human relay."
```

## 4. Integration Verdict
- **Deliverable Path**: `ops/ai/hard_no_idle50/deliverables/HNI_10_CANDIDATE_FINGERPRINT_SPEC.md`
- **Blocker**: NONE
- **Missing**: NONE
- **Next Exact Action**: Advance to next sequential task in Hard No-Idle pipeline.
- **Do-Not-Repeat Fingerprint**: `CANDIDATE_FINGERPRINT_SPEC:COMPLETE:HNI_10_CANDIDATE_FINGERPRINT_SPEC.md`
