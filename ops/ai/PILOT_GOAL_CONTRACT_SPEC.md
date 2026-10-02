# Minimum-Real-Pilot Goal Contract (GQ45)

## Definition of the Pilot
The Courier Pilot is the first time the Courier Motor will dispatch a real, non-trivial coding task to an active AI agent, receive the result, verify it, and apply it, completely isolating the AI agent from direct repository access.

## The Contract
To pass the Minimum-Real-Pilot, the following contract MUST be upheld during execution:

1. **Input Constraint:** The AI agent receives ONLY the `MAC_EXACT_BINDING_INPUTS` containing the task instructions, target files, and current `FINAL_SHA`.
2. **Output Constraint:** The AI agent MUST produce a valid JSON artifact adhering to the Execution Event Schema (GQ35).
3. **No Direct Commits:** The AI agent MUST NOT execute `git commit` or `git push`.
4. **Verification Requirement:** `courier_verifier.py` MUST successfully parse the agent's output, run targeted tests (if provided by the task), check the diff against the allowed scope, and return `VERIFIED`.
5. **No Human Execution:** A human MUST NOT type commands to fix the agent's code. If the agent fails, the task fails and must be re-dispatched.

## Pilot Tasks Candidate List
- Update a specific non-critical unit test to use a new assertion framework.
- Add a new specific metric to the server `/system/metrics` endpoint.
- Correct a typo in a markdown documentation file.

*Note: The Pilot gate remains LOCKED. This contract only prepares the rules of engagement.*
