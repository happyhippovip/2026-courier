# M193 — Tamper-Evident Artifact Verification & Corrupted Byte Rejection Test

## 1. Overview & Authority
- **Task ID**: M193
- **Area**: TAMPER_REJECTION
- **Status**: COMPLETE

## 2. Test Specification
- Harness injects 1-bit inversion into stored artifact payload.
- Verifier requests artifact and recalculates SHA-256.
- Invariant: Verifier triggers `CRYPTOGRAPHIC_MISMATCH_ERROR` and rejects result with exit code non-zero.
