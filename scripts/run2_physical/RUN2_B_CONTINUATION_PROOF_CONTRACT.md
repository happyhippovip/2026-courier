# RUN 2 B CONTINUATION PROOF CONTRACT

## Verification Requirement
RUN 2 must boot, read the durable `RECONCILE` state, skip `VERIFY`, and immediately start `B` autonomously to continue execution from the interrupted point.

## Data Sources
1. RUN 2 Execution state log: `run2_state_snapshot.json`
2. Metric target: `$.state_transitions`

## Verification Rule
```python
def verify_b_continuation(run2_snapshot_path):
    import json
    with open(run2_snapshot_path) as f:
        data = json.load(f)
    
    transitions = data.get('state_transitions', [])
    
    # 1. VERIFY must NOT exist in transitions (it was already done in RUN 1)
    for t in transitions:
        assert t['state'] != 'VERIFY', "RUN 2 executed VERIFY state, which means it failed to read RECONCILE state or restarted from scratch."
        assert 'HUMAN' not in t['state'], "RUN 2 required human intervention. Not autonomous."
    
    # 2. B_START must exist and be the first major state transition post-boot
    b_start_found = any(t['state'] == 'B_START' for t in transitions)
    assert b_start_found, "Process B failed to start during RUN 2 continuation."
```
