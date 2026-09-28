# RUN 1 SERVER BYTES PROOF CONTRACT

## Verification Requirement
The final generated server payload bytes MUST match exactly the expected serialized state output of the execution against `{{FINAL_SHA}}`.

## Data Sources
1. Execution payload: `run1_state_snapshot.json` 
2. Metric target: `$.payload.server_bytes_hash`

## Verification Rule
```python
def verify_server_bytes(snapshot_json_path):
    import json
    import hashlib
    with open(snapshot_json_path) as f:
        data = json.load(f)
    
    # Extract the payload to simulate what the server receives
    payload = data.get('payload', {})
    serialized_payload = json.dumps(payload, sort_keys=True).encode('utf-8')
    computed_hash = hashlib.sha256(serialized_payload).hexdigest()
    
    expected_hash = data.get('expected_server_bytes_hash')
    assert computed_hash == expected_hash, f"Hash mismatch. Expected {expected_hash}, got {computed_hash}"
```
