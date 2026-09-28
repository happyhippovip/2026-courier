# RUN 1 PHYSICAL EVIDENCE LAYOUT

Target Directory: `/tmp/courier_run1_{{FINAL_SHA}}/evidence`

## Expected Files
1. `run1_stdout.log` - Standard output stream of the execution.
2. `run1_stderr.log` - Standard error stream of the execution.
3. `run1_exit_code.txt` - Numerical exit code of the execution.
4. `run1_state_snapshot.json` - Serialized state snapshot immediately after run 1 completion.
5. `run1_system_metrics.json` - CPU, RAM, Network utilization during run.
6. `run1_falsifiability_hash.txt` - SHA256 of all above artifacts for run 1 integrity verification.
