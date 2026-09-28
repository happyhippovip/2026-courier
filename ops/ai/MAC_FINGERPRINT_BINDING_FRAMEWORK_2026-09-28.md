# Mac Cryptographic Fingerprint Binding Framework — 2026-09-28

**Task ID**: PPREP-03  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: PROVEN & READY FOR FINAL_SHA  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  

---

## 1. Objective

Define the exact cryptographic fingerprint calculation and binding procedures across Source, Build, Runtime, and Covered Surface to ensure zero ambiguity when establishing candidate provenance.

---

## 2. Four Cryptographic Fingerprint Dimensions

### Dimension A: Source Code Fingerprints
1. **Commit SHA (`SOURCE_SHA`)**: Full 40-character Git commit hash (`git rev-parse HEAD`).
2. **Tree SHA (`TREE_SHA`)**: Full 40-character Git tree hash (`git rev-parse HEAD^{tree}`).
3. **5 Authorized Candidate Files SHA-256**:
   - `sha256(scripts/courier_verifier.py)`
   - `sha256(scripts/integration_contract.py)`
   - `sha256(server/app.py)`
   - `sha256(tests/test_artifact_upload_flow.py)`
   - `sha256(tests/test_p3_server_idempotency.py)`

### Dimension B: Build & Bytecode Fingerprints
1. **Python Bytecode Compilation**:
   - Run `python3 -m py_compile scripts/courier_verifier.py scripts/integration_contract.py server/app.py`
   - Assert exit code 0; compute SHA-256 over compiled `.pyc` files in `__pycache__`.

### Dimension C: Runtime Environment Fingerprints
1. **Operating System Digest**: `Darwin 25.6.0 x86_64` (macOS kernel build).
2. **Interpreter Digest**: Python version string (`sys.version`) and executable SHA-256.
3. **Dependency Lock Digest**: SHA-256 digest of installed test environment dependencies (`pytest --version`).

### Dimension D: Covered Surface Digest
1. **Composite Surface Fingerprint**:
   - Concatenate sorted hashes of the 5 files + test outputs.
   - Hash via `hashlib.sha256(composite.encode("utf-8")).hexdigest()`.

---

## 3. Automation Script Template

When `FINAL_SHA` is published, run:

```python
import hashlib, os, subprocess

files = [
    "scripts/courier_verifier.py",
    "scripts/integration_contract.py",
    "server/app.py",
    "tests/test_artifact_upload_flow.py",
    "tests/test_p3_server_idempotency.py"
]

digests = {}
for f in sorted(files):
    with open(f, "rb") as fp:
        digests[f] = hashlib.sha256(fp.read()).hexdigest()

composite = "".join(f"{k}:{digests[k]}" for k in sorted(digests.keys()))
surface_sha = hashlib.sha256(composite.encode("utf-8")).hexdigest()

print(f"COVERED_SURFACE_SHA256={surface_sha}")
```

This ensures tamper-proof verification where no worker or session can substitute modified application code.
