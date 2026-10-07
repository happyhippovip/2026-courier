# PP001: Mac Canary Physical Execution

## Target
`scripts/courier_verifier.py`
`scripts/run_chief_commander.py`
`ops/ai/WALL_QUEUE_CURRENT.md`

## Defect / Blocker
The system requires physical verification of the `RUN1` / `N1` test matrix to ensure non-simulation and true hardware attestation. Windows and synthetic nodes are unable to perform this task as it is strictly gated to the Mac environment and a physical operator.

## Instructions for PHYSICAL_OWNER (Mac)
1. Pull the latest candidate SHA (`34b0a4264bf763bc2a78f761ffba36e47706b2cf`).
2. Execute the verification suite: `python -m pytest tests/` and run the ledger execution `python scripts/run_chief_commander.py --mode=run1`.
3. Capture the forensic hardware signature and test output logs.
4. Commit the results to the results folder and advance `WALL_QUEUE_CURRENT.md` from `TRUE_IDLE / AWAIT_MAC_CANARY` to the next phase (e.g. `CORE_FREEZE` or `RUN2_PREP`).

## Causal Path
To prevent AI hallucination or "false green" states, the system demands that key transition points be executed and signed by a trusted, physical execution node (the Mac Canary).
