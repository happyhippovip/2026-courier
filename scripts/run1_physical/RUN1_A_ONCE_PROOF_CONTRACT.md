# RUN 1 A-ONCE PROOF CONTRACT

## Metric: `A_EXECUTION_COUNT`
- **Expected Value**: `1`
- **Description**: Verification that Process A executes exactly once during RUN 1.

## Evidence Source
File: `run1_state_snapshot.json`
Path: `$.execution_counters.process_a`

## Verification Rule
```python
def verify_a_once(snapshot_json_path):
    import json
    with open(snapshot_json_path) as f:
        data = json.load(f)
    a_count = data.get('execution_counters', {}).get('process_a', 0)
    assert a_count == 1, f"Expected Process A count 1, got {a_count}"
```
