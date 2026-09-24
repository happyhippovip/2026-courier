# P4: Pilot Execution Plan (Solo-Pilot)

This document describes the execution plan for the P4 phase: completing a full, end-to-end customer pilot without mocked components.

## 1. Pilot Selection (Der Solo-Pilot)
To avoid building parallel, unvalidated marketing examples, P4 focuses on a single, scoped pilot customer: **Courier Documentation Generation**.
- **Customer Identity:** Internal/Dogfooding user acting as a solo developer.
- **Request:** Generate the `docs/public_site` using the actual Courier repository as context.
- **Why this pilot?** It tests heavy file reading, processing, LLM token limits, and filesystem writing (the exact workflow a real developer community needs) without requiring external third-party API keys or unverified SaaS credentials.

## 2. Execution Flow (Ablauf)
1. **Intake:** The pilot request is parsed by the planner (Opus).
2. **Goal Creation:** A new `goal.json` is constructed in the `central_state.json` containing specific subtasks (`TASK-DOC-1` through `TASK-DOC-10`).
3. **Dispatch:** The server dispatches tasks to active workers (Mac for Unix tasks, Windows for path-testing tasks).
4. **Execution:** Workers use the Anti-Gravity (`agy`) CLI locally. *Crucially, they must run with the P2/P3 timeout fixes (timeout > 300s) to survive long `agy` reasoning loops.*
5. **Reconciliation:** Workers post `RESULT_RECEIVED`. The `courier_continue.py` loop validates the Ledger and declares `CLEAN_IDLE_ACHIEVED`.

## 3. Sandbox Payments (Zahlungen in der Sandbox)
- **Requirement:** Payments must initially use a Sandbox.
- **Implementation:** A simple virtual balance check before Goal acceptance.
- **Flow:**
  - Pilot user balance starts at 10.00 (Virtual EUR).
  - Estimated task cost (e.g., 2.50 EUR) is deducted provisionally.
  - If actual cost exceeds the provision, the task halts (`402 Payment Required`).
  - No external stripe API integration is permitted in P4 to maintain architectural simplicity.

## 4. External Approvals (Externe Freigaben)
- **Requirement:** External approvals must be handled separately.
- **Implementation:** When the Worker completes the documentation, it does NOT push to GitHub automatically. Instead, it creates a local commit and changes the Goal status to `HUMAN_REQUIRED` (Wait for Human).
- The human user verifies the output and manually pushes, after which the Agent resumes and closes the Goal.

## 5. Definition of Done (Abnahmekriterien)
- The entire goal (`P4-SOLO-PILOT`) transitions from `READY` to `DONE`.
- At least one task is handled by the Mac worker, and one by the Windows worker.
- The `agent_handoff_ledger.json` reflects all 10 unproven edges as successfully proven.
- No parallel architecture was built.
