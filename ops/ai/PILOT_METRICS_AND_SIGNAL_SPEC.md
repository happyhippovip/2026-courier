# Pilot Metrics & Value Signal Spec (GQ46, GQ47)

## GQ46: Pilot Metrics
To objectively evaluate the success of Courier's Pilot Phase, the following metrics MUST be collected during execution:

1. **Setup Time (T_setup):** Wall-clock time from fetching the latest `FINAL_SHA` to a ready worker polling the server. Target: < 5 minutes.
2. **Human Interventions Per Goal (HIPG):** The number of manual actions required by a human operator to complete the goal (e.g., resolving a merge conflict, restarting a crashed script, manually entering a missing API key). Target: Exactly 0.
3. **Run Success Rate (RSR):** Percentage of dispatched tasks that reach the `VERIFIED` state successfully on the first try. Target: > 80%.
4. **No Duplicate Rate (NDR):** Percentage of tasks that are executed exactly once across crashes or restarts. Target: 100%.
5. **Support Effort:** Qualitative measure of how much context setting or hand-holding the AI provider required to understand the Courier constraints. Target: Zero out-of-band prompting.
6. **Provider Cost Class:** Estimated monetary cost per successfully verified task (e.g., $0.05 per task). Target: Low/Sustainable.
7. **Time to Useful Result (TTUR):** Total wall-clock time from task creation to verified output stored securely. Target: < 2 minutes per small task.

## GQ47: Pilot Value Signal Definitions
The Product-Shell-Gate (GQ48) will ONLY be unlocked if the Pilot Value Signal is strictly Positive.

### Positive Value Signal (GREEN)
- RSR > 80%
- HIPG == 0 (Zero human interventions)
- NDR == 100%
- The resulting code diff applies cleanly and targeted tests pass.
- **Action:** Proceed to UNLOCK Product-Shell-Gate.

### Unclear Value Signal (YELLOW)
- HIPG == 0, but RSR < 80% due to provider-specific hallucinations (e.g., writing syntax errors).
- The Courier engine performed correctly (isolated the failure, rejected the bad code, re-queued the task), but the task itself was not completed efficiently.
- **Action:** DO NOT UNLOCK. Adjust provider prompts or use a more capable AI model, then re-run pilot.

### Negative Value Signal (RED)
- HIPG > 0 (A human had to intervene to save the system).
- NDR < 100% (The same task was executed twice, duplicating effort/cost).
- The verifier accepted a malicious or out-of-scope file change.
- The daemon crashed and failed to recover its state.
- **Action:** DO NOT UNLOCK. Halt pilot. Identify root cause in Courier infrastructure, implement structural fix, restart RUN_1/RUN_2 phase proofs.
