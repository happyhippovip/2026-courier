# M229: Run2 Witness Package

## Goal
Prove that the resumption engine (Run 2) cleanly appends its forensic activity to the existing state without contaminating the Run 1 Witness Package.

## Implementation & Proof
1. **Log Rotation & Segregation**:
   - `run_2_mac.sh` initiates a secondary logging suite (`logs/server_run2.log`, `logs/worker_run2.log`), ensuring that Run 1's physical execution logs are never overwritten or conflated.
2. **State Machine Delta**:
   - Courier's state machine accurately parses the restored `state.json` and updates entity statuses across the timeline. Resumed tasks shift from `"HUMAN_REQUIRED"` to `"QUEUED"`, accumulating attempts and generating new `attempt_id`s. 
3. **Traceability**:
   - The separation of Run 1 and Run 2 logs, coupled with the unified linear state JSON (which tracks `restarted_at` and `attempts`), forms a complete and auditable Run 2 Witness Package.

## Conclusion
Courier strictly delineates execution timelines by segregating logging output while natively supporting structured resumption via its unified state backend.
