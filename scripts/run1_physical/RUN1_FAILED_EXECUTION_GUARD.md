# RUN 1 FAILED EXECUTION CONTAMINATION GUARD

## Principle
If a physical RUN fails (non-zero exit code), its artifacts MUST be perfectly isolated and must never be permitted to serve as the baseline for `RUN_2` (continuation/restart logic).

## Guard Verification Logic
```python
def verify_success_no_contamination(exit_code_path, snapshot_path):
    import json
    
    # 1. Exit code must strictly be 0
    with open(exit_code_path, 'r') as f:
        exit_code = f.read().strip()
    assert exit_code == "0", f"CRITICAL: Failed execution detected (Exit Code {exit_code}). Artifacts are marked contaminated."
    
    # 2. Internal state snapshot must report SUCCESS
    with open(snapshot_path, 'r') as f:
        data = json.load(f)
        
    final_status = data.get('final_status', 'UNKNOWN')
    assert final_status == 'SUCCESS', f"CRITICAL: Snapshot reports {final_status}. Cannot proceed to RUN_2."
```

## Remediation
If this guard fails, the host environment must be completely reset. A failure in RUN 1 means the candidate bundle is rejected by physical falsification.
