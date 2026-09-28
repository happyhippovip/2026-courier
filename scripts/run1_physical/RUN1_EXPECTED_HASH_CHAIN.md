# RUN 1 EXPECTED HASH CHAIN

## Components
1. **Target Execution SHA**: `{{FINAL_SHA}}`
2. **Artifact Final Hash**: Generated post-execution in `run1_falsifiability_hash.txt`
3. **Ledger Block Hash**: Bound to the overall completion ledger entry of RUN 1.

## Hash Chain Logic
The integrity is preserved by:
```python
def compute_run1_chain(final_sha, execution_artifacts_dir):
    import hashlib
    import glob
    
    # 1. Combine output files in deterministic order
    hasher = hashlib.sha256()
    hasher.update(final_sha.encode('utf-8'))
    
    files = sorted(glob.glob(f"{execution_artifacts_dir}/*.log") + glob.glob(f"{execution_artifacts_dir}/*.json"))
    for f in files:
        with open(f, 'rb') as fd:
            hasher.update(fd.read())
            
    # 2. Output the expected artifact integrity hash
    return hasher.hexdigest()
```
