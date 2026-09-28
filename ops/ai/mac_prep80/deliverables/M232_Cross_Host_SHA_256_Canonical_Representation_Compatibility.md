# M232 — Cross-Host SHA-256 Canonical Representation Compatibility

## 1. Overview & Authority
- **Task ID**: M232
- **Area**: CRLF_COMPATIBILITY
- **Status**: COMPLETE

## 2. Compatibility Invariants
- Binary artifacts are hashed byte-for-byte with no text conversions.
- Text manifests enforce Unix LF (`\n`) standard before hashing.
- Eliminates Windows CRLF vs Mac LF hash discrepancies.
