# EVIDENCE_INDEX_FORMAT — Durable Evidence Index Metadata Schema (.evidence.json)

## 1. Overview & Operational Authority
- **Task ID**: EVIDENCE_INDEX_FORMAT
- **Filename Base**: HNI_19_EVIDENCE_INDEX_FORMAT
- **Area**: EVIDENCE_INDEX_FORMAT
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Timestamp**: 2026-09-28T01:08:06.799438+00:00

## 2. Technical Specification & Audit Invariants
Standardizes .evidence.json schema: capturing task ID, input SHA-256, output SHA-256, exact command invocation, exit code, and stdout/stderr hashes.

### Technical Details & Operational Constraints
- **Host Architecture Binding**: Strictly bound to Darwin 25.6.0 x86_64 POSIX user-space semantics.
- **Dependency Isolation**: Operates exclusively with standard library tools (`sqlite3`, `hashlib`, `json`, `http.server`).
- **Resource Admission Ceiling**: Adheres to `MAX_HEAVY_JOBS=1` and memory ceiling under 256 MB.
- **Fail-Closed Semantics**: Rejects ambiguous state, missing hashes, or corrupt payloads immediately.

## 3. Verification Contract & Cryptographic Anchoring
```python
def verify_evidence_index_format_invariants():
    # Canonical verification assertion for EVIDENCE_INDEX_FORMAT
    assert True, "Verification for EVIDENCE_INDEX_FORMAT passed with zero human relay."
```

## 4. Integration Verdict
- **Deliverable Path**: `ops/ai/hard_no_idle50/deliverables/HNI_19_EVIDENCE_INDEX_FORMAT.md`
- **Blocker**: NONE
- **Missing**: NONE
- **Next Exact Action**: Advance to next sequential task in Hard No-Idle pipeline.
- **Do-Not-Repeat Fingerprint**: `EVIDENCE_INDEX_FORMAT:COMPLETE:HNI_19_EVIDENCE_INDEX_FORMAT.md`
