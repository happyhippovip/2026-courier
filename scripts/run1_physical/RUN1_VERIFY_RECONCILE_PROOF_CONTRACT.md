# RUN 1 VERIFY -> RECONCILE PROOF CONTRACT

## Verification Requirement
The execution MUST complete the `VERIFY` phase BEFORE it enters the `RECONCILE` phase, and the durable transition packet must log these states in the exact correct order with monotonically increasing timestamps.

## Data Sources
1. Execution state log: `run1_state_snapshot.json`
2. Metric target: `$.state_transitions`

## Verification Rule
```python
def verify_state_transitions(snapshot_json_path):
    import json
    with open(snapshot_json_path) as f:
        data = json.load(f)
    
    transitions = data.get('state_transitions', [])
    
    verify_time = -1
    reconcile_time = -1
    
    for t in transitions:
        if t['state'] == 'VERIFY':
            verify_time = t['timestamp']
        elif t['state'] == 'RECONCILE':
            reconcile_time = t['timestamp']
            
    assert verify_time != -1, "VERIFY state not found in transitions"
    assert reconcile_time != -1, "RECONCILE state not found in transitions"
    assert verify_time < reconcile_time, f"VERIFY time ({verify_time}) must strictly precede RECONCILE time ({reconcile_time})"
```
