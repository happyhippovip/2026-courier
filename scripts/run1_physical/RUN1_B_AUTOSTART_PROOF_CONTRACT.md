# RUN 1 B-AUTOSTART PROOF CONTRACT

## Verification Requirement
The `B` process MUST autostart automatically without human intervention after `A` completes verification successfully.

## Data Sources
1. Execution state log: `run1_state_snapshot.json`
2. Metric target: `$.execution_counters.process_b` and `$.state_transitions`

## Verification Rule
```python
def verify_b_autostart(snapshot_json_path):
    import json
    with open(snapshot_json_path) as f:
        data = json.load(f)
    
    # 1. B must have started
    b_count = data.get('execution_counters', {}).get('process_b', 0)
    assert b_count > 0, "Process B did not start"
    
    # 2. B's start time must follow A's completion with minimal latency and no human approval node
    transitions = data.get('state_transitions', [])
    
    a_end = -1
    b_start = -1
    for t in transitions:
        if t['state'] == 'A_COMPLETE':
            a_end = t['timestamp']
        elif t['state'] == 'B_START':
            b_start = t['timestamp']
        elif t['state'] == 'HUMAN_INTERVENTION':
            assert False, "Found HUMAN_INTERVENTION state - B did not autostart purely autonomously."
            
    assert a_end != -1, "A_COMPLETE state not found"
    assert b_start != -1, "B_START state not found"
    assert b_start > a_end, f"B_START ({b_start}) must occur after A_COMPLETE ({a_end})"
```
