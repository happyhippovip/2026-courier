# M196 — Task Goal Pre-Declared Hash vs Server Storage Hash Verification

## 1. Overview & Authority
- **Task ID**: M196
- **Area**: HASH_VERIFICATION
- **Status**: COMPLETE

## 2. Verification Mapping
- Goal contract: Declares `expected_sha256`.
- Server storage: Computes `stored_sha256 = sha256(open(path, 'rb').read())`.
- Verifier attestation: Asserts `expected_sha256 == stored_sha256`.
