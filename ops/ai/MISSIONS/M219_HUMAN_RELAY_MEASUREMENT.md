# M219: Human Relay Measurement

## Goal
Prove that the Courier system is capable of measuring exactly how much human delay (relay time) is incurred when manual intervention is required.

## Implementation & Proof
1. **Quarantine Timestamping**:
   - In `server/app.py` (`reclaim_stale`), when a task is moved to `"HUMAN_REQUIRED"`, the control plane timestamps the exact moment:
     ```python
     task["restarted_at"] = time.time()
     ```
2. **Resumption Tracking**:
   - When the operator issues a `/tasks/resume` via the command line or UI, Courier records `"resumed_from": status` and pushes the task back to `"QUEUED"`. 
   - Additionally, the time differential between `restarted_at` and the resumption event allows the system to empirically calculate the human relay latency.

## Conclusion
Courier tracks the boundaries of manual intervention natively in the task metadata, enabling exact measurement of the human relay penalty.
