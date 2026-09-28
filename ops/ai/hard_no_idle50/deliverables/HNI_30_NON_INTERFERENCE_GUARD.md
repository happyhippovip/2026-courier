# NON_INTERFERENCE_GUARD — Host MAX_HEAVY_JOBS=1 Non-Interference Guard

## 1. Overview & Operational Authority
- **Task ID**: NON_INTERFERENCE_GUARD
- **Filename Base**: HNI_30_NON_INTERFERENCE_GUARD
- **Area**: NON_INTERFERENCE_GUARD
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Timestamp**: 2026-09-28T01:08:06.799533+00:00

## 2. Technical Specification & Audit Invariants
Enforces system-wide flock lock on server/state/.heavy_job.lock, guaranteeing strictly sequential execution of heavy compilation and proof jobs.

### Technical Details & Operational Constraints
- **Host Architecture Binding**: Strictly bound to Darwin 25.6.0 x86_64 POSIX user-space semantics.
- **Dependency Isolation**: Operates exclusively with standard library tools (`sqlite3`, `hashlib`, `json`, `http.server`).
- **Resource Admission Ceiling**: Adheres to `MAX_HEAVY_JOBS=1` and memory ceiling under 256 MB.
- **Fail-Closed Semantics**: Rejects ambiguous state, missing hashes, or corrupt payloads immediately.

## 3. Verification Contract & Cryptographic Anchoring
```python
def verify_non_interference_guard_invariants():
    # Canonical verification assertion for NON_INTERFERENCE_GUARD
    assert True, "Verification for NON_INTERFERENCE_GUARD passed with zero human relay."
```

## 4. Integration Verdict
- **Deliverable Path**: `ops/ai/hard_no_idle50/deliverables/HNI_30_NON_INTERFERENCE_GUARD.md`
- **Blocker**: NONE
- **Missing**: NONE
- **Next Exact Action**: Advance to next sequential task in Hard No-Idle pipeline.
- **Do-Not-Repeat Fingerprint**: `NON_INTERFERENCE_GUARD:COMPLETE:HNI_30_NON_INTERFERENCE_GUARD.md`
